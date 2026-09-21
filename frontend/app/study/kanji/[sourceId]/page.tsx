import { StudyDetailView } from "@/components/StudyDetail";

export default async function KanjiStudyPage({ params }: { params: Promise<{ sourceId: string }> }) {
  const { sourceId } = await params;
  return <StudyDetailView kind="kanji" sourceId={sourceId} />;
}
