/**
 * Postgres bağlantı + auth operations.
 */
import { Pool } from "pg";
import bcrypt from "bcrypt";

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  // build sırasında throw etmeyelim — runtime'da kontrol
  console.warn("DATABASE_URL is not set");
}

let _pool: Pool | null = null;

export function getPool(): Pool {
  if (!_pool) {
    if (!DATABASE_URL) throw new Error("DATABASE_URL is required");
    _pool = new Pool({
      connectionString: DATABASE_URL,
      max: 10,
      idleTimeoutMillis: 30_000,
    });
  }
  return _pool;
}

export type DbUser = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  password_hash: string | null;
  is_active: boolean;
};

export async function getUserByEmail(email: string): Promise<DbUser | null> {
  const pool = getPool();
  const res = await pool.query<DbUser>(
    `SELECT id, email, name, role, password_hash, is_active
     FROM users WHERE email = $1`,
    [email],
  );
  return res.rows[0] ?? null;
}

export async function authenticateUser(
  email: string,
  password: string,
): Promise<Omit<DbUser, "password_hash"> | null> {
  const user = await getUserByEmail(email);
  if (!user || !user.is_active || !user.password_hash) return null;
  const ok = await bcrypt.compare(password, user.password_hash);
  if (!ok) return null;

  // last_login_at güncelle
  await getPool().query(
    `UPDATE users SET last_login_at = NOW() WHERE id = $1`,
    [user.id],
  );

  const { password_hash: _, ...rest } = user;
  return rest;
}

export async function createUser(opts: {
  email: string;
  password: string;
  name?: string | null;
  kvkkAccepted: boolean;
  marketingConsent?: boolean;
}): Promise<DbUser> {
  if (!opts.kvkkAccepted) {
    throw new Error("KVKK aydınlatma metni onayı zorunlu.");
  }
  const hash = await bcrypt.hash(opts.password, 12);
  const pool = getPool();
  // Kayıt = bootstrap: user + tenant + ilk üyelik atomik olmalı. Ayrıca
  // tenant_members RLS INSERT politikası app.current_user_id bekliyor; bu yüzden
  // hepsini tek client + tek transaction içinde, context set ederek yapıyoruz.
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    const res = await client.query<DbUser>(
      `INSERT INTO users (email, name, password_hash, kvkk_accepted_at, marketing_consent)
       VALUES ($1, $2, $3, NOW(), $4)
       RETURNING id, email, name, role, password_hash, is_active`,
      [opts.email.toLowerCase(), opts.name ?? null, hash, !!opts.marketingConsent],
    );
    const user = res.rows[0];

    // RLS context'i (transaction-local). tenant_members INSERT politikası bunu ister.
    await client.query(`SELECT set_config('app.current_user_id', $1, true)`, [user.id]);

    // Otomatik solo tenant oluştur (Free plan)
    const tenant = await client.query<{ id: string }>(
      `INSERT INTO tenants (name, slug, type, plan_tier, max_users)
       VALUES ($1, $2, 'solo', 'free', 1)
       RETURNING id`,
      [
        `${opts.name || opts.email.split("@")[0]}'in Çalışma Alanı`,
        `solo-${user.id.slice(0, 8)}`,
      ],
    );

    await client.query(
      `INSERT INTO tenant_members (tenant_id, user_id, role, accepted_at)
       VALUES ($1, $2, 'owner', NOW())`,
      [tenant.rows[0].id, user.id],
    );

    await client.query("COMMIT");
    return user;
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}

export async function emailTaken(email: string): Promise<boolean> {
  const u = await getUserByEmail(email);
  return !!u;
}

/**
 * Kullanıcının GÜNCEL rolünü DB'den okur (JWT'deki olası eski rol yerine).
 * Admin yetkisi gibi kritik kontroller için kaynak-doğruluk. Pasif/yok → null.
 */
export async function getUserRole(userId: string): Promise<string | null> {
  const pool = getPool();
  const res = await pool.query<{ role: string; is_active: boolean }>(
    `SELECT role, is_active FROM users WHERE id = $1`,
    [userId],
  );
  const r = res.rows[0];
  if (!r || !r.is_active) return null;
  return r.role;
}
