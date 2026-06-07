"""Türk Hukuk Emsal Karar Arama — Streamlit demo UI.

Çalıştır:
  streamlit run app/streamlit_app.py --server.fileWatcherType none
"""
from __future__ import annotations
import sys
from pathlib import Path

import duckdb
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Türk Hukuk Emsal Arama",
    page_icon="⚖️",
    layout="wide",
)


@st.cache_resource
def load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("intfloat/multilingual-e5-base", device="cpu")


@st.cache_resource
def load_chroma():
    import chromadb
    client = chromadb.PersistentClient(path=str(ROOT / "data" / "chroma_db"))
    return client.get_collection(name="hukuk_kararlari")


@st.cache_data
def get_full_decision(decision_id: str) -> dict | None:
    """Parquet'ten tam karar metnini ve metadata'yı çek."""
    parquet = ROOT / "data" / "final" / "all_decisions.parquet"
    if not parquet.exists():
        return None
    try:
        rows = duckdb.sql(
            f"SELECT * FROM '{parquet}' WHERE id = '{decision_id}' LIMIT 1"
        ).fetchall()
        cols = duckdb.sql(f"SELECT * FROM '{parquet}' LIMIT 0").columns
        if not rows:
            return None
        return dict(zip(cols, rows[0]))
    except Exception as e:
        st.error(f"Parquet sorgu hatası: {e}")
        return None


def search(query: str, k: int, filters: dict | None = None):
    model = load_model()
    col = load_chroma()
    q_text = f"query: {query}"
    q_emb = model.encode([q_text], normalize_embeddings=True).tolist()
    where = {kk: vv for kk, vv in (filters or {}).items() if vv and vv != "Tümü"}
    return col.query(
        query_embeddings=q_emb,
        n_results=k,
        where=where if where else None,
    )


st.title("⚖️ Türk Hukuk Emsal Karar Arama")
st.caption("İcra · Tahsilat · İhtar konularında Yargıtay · Danıştay · AİHM emsal araması")

with st.sidebar:
    st.header("Filtreler")
    source = st.selectbox("Kaynak", ["Tümü", "yargitay", "danistay", "hudoc"])
    chamber_options = [
        "Tümü", "12. Hukuk Dairesi", "8. Hukuk Dairesi", "13. Hukuk Dairesi",
        "19. Hukuk Dairesi", "3. Hukuk Dairesi",
        "13. Daire", "İdare Dava Daireleri Kurulu",
        "Vergi Dava Daireleri Kurulu", "3. Daire", "4. Daire", "8. Daire",
        "9. Daire", "10. Daire",
    ]
    chamber = st.selectbox("Daire", chamber_options)
    top_k = st.slider("Kaç sonuç gösterilsin?", 1, 20, 5)

query = st.text_input(
    "Hukuki konunuzu serbestçe yazın:",
    placeholder="Örn: İcra takibinde emekli maaşının haczi mümkün mü?",
)

if st.button("Ara", type="primary") and query.strip():
    filters = {}
    if source != "Tümü":
        filters["source"] = source
    if chamber != "Tümü":
        filters["court_chamber"] = chamber

    with st.spinner("Emsal kararlar aranıyor..."):
        results = search(query, top_k, filters)

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    if not docs:
        st.warning("Filtre kriterlerinize uygun sonuç bulunamadı.")
    else:
        st.success(f"{len(docs)} emsal karar bulundu.")
        st.caption("💡 Sonuçlar kararın **en uyumlu parçasını** gösterir. "
                   "Tam karar metnini görmek için ilgili sonucu açın.")

        for i, (doc, meta, dist, cid) in enumerate(zip(docs, metas, distances, ids), 1):
            similarity = 1 - dist
            header = (f"#{i} — {meta.get('court_chamber', '?')} · "
                      f"{meta.get('case_no', '?')} → {meta.get('decision_no', '?')} · "
                      f"{meta.get('decision_date', '?')}   "
                      f"(benzerlik: {similarity:.2%})")
            with st.expander(header, expanded=(i <= 2)):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("**Sorguya uyan kısım:**")
                    st.write(doc)

                    # Tam karar metni — toggle ile aç
                    decision_id = meta.get("decision_id", "")
                    if decision_id:
                        show_full = st.checkbox(
                            "📖 Tam karar metnini göster",
                            key=f"full_{cid}",
                        )
                        if show_full:
                            full = get_full_decision(decision_id)
                            if full and full.get("cleaned_text"):
                                full_text = full["cleaned_text"]
                                st.markdown(
                                    f"**Tam karar metni** "
                                    f"({len(full_text):,} karakter):"
                                )
                                st.text_area(
                                    label="full_text_box",
                                    value=full_text,
                                    height=400,
                                    key=f"ta_{cid}",
                                    label_visibility="collapsed",
                                )
                            else:
                                st.warning("Tam karar metni bulunamadı "
                                           f"(id: {decision_id})")

                with col2:
                    st.markdown("**Metadata**")
                    st.markdown(f"- **Kaynak:** {meta.get('source', '?')}")
                    st.markdown(f"- **Daire:** {meta.get('court_chamber', '?')}")
                    st.markdown(f"- **Esas:** {meta.get('case_no', '-')}")
                    st.markdown(f"- **Karar:** {meta.get('decision_no', '-')}")
                    st.markdown(f"- **Tarih:** {meta.get('decision_date', '-')}")
                    st.markdown(f"- **Konular:** {meta.get('topic_tags', '-')}")
                    url = meta.get("source_url", "")
                    if url and url.startswith("http"):
                        st.markdown(f"[🔗 Kaynak sayfa]({url})")

with st.sidebar:
    st.divider()
    st.caption("Dataset")
    try:
        col = load_chroma()
        st.metric("Chunk", f"{col.count():,}")
    except Exception:
        st.warning("Chroma yüklenemedi. embed.py çalıştırılmış mı?")
    try:
        parquet = ROOT / "data" / "final" / "all_decisions.parquet"
        if parquet.exists():
            n = duckdb.sql(f"SELECT COUNT(*) FROM '{parquet}'").fetchone()[0]
            st.metric("Karar", f"{n:,}")
    except Exception:
        pass
