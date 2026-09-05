import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownTextImpl() {
  return (
    <MarkdownTextPrimitive
      className="message-markdown"
      remarkPlugins={[remarkGfm]}
      components={{
        img: () => null,
        a: ({ children, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer">
            {children}
          </a>
        ),
      }}
    />
  );
}
