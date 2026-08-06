import { toDisplayMessage } from '../api/apiError';
import { useLlmSystemPromptQuery } from '../domains/ai-intelligence/useLlmSystemPromptQuery';

export default function LlmSystemPromptCard() {
  const query = useLlmSystemPromptQuery();

  return (
    <div className="rounded-xl overflow-hidden border border-outline-variant dark:border-outline-variant/30">
      <div className="flex items-center justify-between px-5 py-4 bg-surface-container-lowest dark:bg-surface-container-high/10 border-b border-outline-variant dark:border-outline-variant/30">
        <p className="flex items-center gap-2 text-label-lg font-semibold text-on-surface dark:text-on-background">
          <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-container/10 dark:bg-primary-fixed-dim/10 text-primary-container dark:text-primary-fixed-dim">
            <span className="material-symbols-outlined text-lg">terminal</span>
          </span>
          LLM System Prompt
        </p>
        {query.data ? (
          <span className="px-2.5 py-1 rounded-full bg-surface-container-high dark:bg-surface-container-high/20 text-label-md text-on-surface-variant dark:text-surface-variant">
            {query.data.promptVersion}
          </span>
        ) : null}
      </div>

      <div className="p-5 space-y-3">
        <p className="text-body-md text-on-surface-variant dark:text-surface-variant">
          Instruksi persis yang dikirim sebagai <code>system_instruction</code> ke Gemini setiap kali
          AI Reasoning digenerate.
        </p>

        {query.isLoading ? (
          <div className="h-48 rounded-lg bg-surface-container-high/40 dark:bg-surface-container-high/10 animate-pulse" />
        ) : query.isError || !query.data ? (
          <p className="flex items-center gap-1.5 text-body-md text-on-surface-variant dark:text-surface-variant">
            <span className="material-symbols-outlined text-lg">error</span>
            {toDisplayMessage(query.error)}
          </p>
        ) : (
          <textarea
            readOnly
            value={query.data.systemInstruction}
            rows={16}
            spellCheck={false}
            className="w-full resize-y rounded-lg border border-outline-variant dark:border-outline-variant/30 bg-surface-container dark:bg-surface-container-high/10 p-3 text-body-md text-on-surface dark:text-on-background leading-relaxed focus:outline-none"
          />
        )}

        <p className="flex items-center gap-1.5 text-label-sm text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined text-base">lock</span>
          Read-only untuk saat ini — belum bisa diedit lewat UI.
        </p>
      </div>
    </div>
  );
}
