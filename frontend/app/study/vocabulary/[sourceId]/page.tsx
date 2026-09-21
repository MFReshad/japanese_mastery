import { StudyDetailView } from "@/components/StudyDetail";

export default async function VocabularyStudyPage({ params }: { params: Promise<{ sourceId: string }> }) {
  const { sourceId } = await params;
  return <StudyDetailView kind="vocabulary" sourceId={sourceId} />;
}
