import {
  AssistantRuntimeProvider,
  type AppendMessage,
  type ThreadMessageLike,
  useExternalStoreRuntime,
} from "@assistant-ui/react";
import { type ReactNode, useCallback } from "react";
import { api } from "../api";
import type { Message, Session } from "../types";

type Props = {
  session: Session;
  disabled: boolean;
  onSession: (session: Session) => void;
  onError: (error: unknown) => void;
  children: ReactNode;
};

const convertMessage = (message: Message): ThreadMessageLike => ({
  id: message.id,
  role: message.role,
  content: [{ type: "text", text: message.content }],
  createdAt: new Date(message.created_at),
});

export function BridgeRuntimeProvider({
  session,
  disabled,
  onSession,
  onError,
  children,
}: Props) {
  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((part): part is Extract<typeof part, { type: "text" }> => part.type === "text")
        .map((part) => part.text)
        .join("\n")
        .trim();
      if (!text || disabled) return;

      try {
        onSession(await api.sendMessage(session.id, text));
      } catch (error) {
        onError(error);
        throw error;
      }
    },
    [disabled, onError, onSession, session.id],
  );

  const runtime = useExternalStoreRuntime({
    messages: session.messages,
    convertMessage,
    isRunning: session.status === "thinking" || session.status === "running",
    isSendDisabled: disabled,
    onNew,
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
