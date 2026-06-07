import { DocPanel } from "./doc-panel";

export const dynamic = "force-dynamic";

export default function DocDetailPage({ params }: { params: { id: string } }) {
  return <DocPanel docId={params.id} />;
}
