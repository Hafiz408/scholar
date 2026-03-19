import KnowledgeUpload from '@/components/KnowledgeUpload'

export default function KnowledgePage() {
  return (
    <main className="max-w-2xl mx-auto py-10 px-4">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Knowledge Base</h1>
      <KnowledgeUpload />
    </main>
  )
}
