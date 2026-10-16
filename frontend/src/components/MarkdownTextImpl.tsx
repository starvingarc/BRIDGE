import { researcherText } from "../researcherLabels";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

type TextNode = { type: string; value?: string; children?: TextNode[] };
function researcherLabels() {
  return (tree: TextNode) => {
    function visit(node: TextNode) {
      if (["text", "inlineCode", "code"].includes(node.type) && typeof node.value === "string") node.value = researcherText(node.value);
      node.children?.forEach(visit);
    }
    visit(tree);
  };
}

export function MarkdownTextImpl({ researcher = false }: { researcher?: boolean }) {
  return (
    <MarkdownTextPrimitive
      className="message-markdown"
      remarkPlugins={researcher ? [remarkGfm, researcherLabels] : [remarkGfm]}
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
