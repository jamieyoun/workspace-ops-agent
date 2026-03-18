import PageDetailClient from "./PageDetailClient";

export default async function PageDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PageDetailClient pageId={id} />;
}
