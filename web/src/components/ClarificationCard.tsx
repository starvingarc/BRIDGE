import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import type { Clarification, ClarificationAnswer } from "../types";

type Props = {
  card: Clarification;
  busy: boolean;
  onAnswer: (answers: ClarificationAnswer[]) => Promise<void>;
  onCancel: () => Promise<void>;
  onRevise: () => Promise<void>;
};
type EditableAnswer = ClarificationAnswer & { other: boolean };

export function ClarificationCard({ card, busy, onAnswer, onCancel, onRevise }: Props) {
  const [answers, setAnswers] = useState<EditableAnswer[]>(() => card.questions.map((question) => ({
    field: question.field, selected: [], text: "", unknown: false, other: false,
  })));
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const perform = async (operation: () => Promise<void>) => {
    if (working || busy) return;
    setWorking(true);
    setError(null);
    try { await operation(); }
    catch (cause) {
      if (mounted.current) setError(cause instanceof ApiError && cause.status === 409
        ? "问题或资料已变化，请重新核对当前问题。"
        : "答案暂未保存，请重试。");
    } finally {
      if (mounted.current) setWorking(false);
    }
  };
  const update = (index: number, change: (answer: EditableAnswer) => EditableAnswer) => {
    setAnswers((current) => current.map((answer, position) => position === index ? change(answer) : answer));
  };
  const disabled = busy || working;
  const ready = answers.every((answer) => answer.unknown || answer.selected.length > 0 || answer.text.trim());
  const labels = { pending: "需要你确认", answered: "已回答", cancelled: "已跳过",
    stale: "相关资料已变化，请重新核对", superseded: "已由新问题替代" };

  return <section className="clarification-card" aria-label="对话问题">
    <header><strong>{labels[card.status]}</strong></header>
    {card.status === "pending" ? (
      <form onSubmit={(event) => {
        event.preventDefault();
        if (ready) void perform(() => onAnswer(answers.map(({ other: _other, ...answer }) => answer)));
      }}>
        {card.questions.map((question, index) => {
          const answer = answers[index];
          const name = card.id + ":" + question.field;
          return <fieldset key={question.field} disabled={disabled}>
            <legend>{question.title}</legend>
            <p className="clarification-reason">{question.reason}</p>
            <div className="clarification-options">
              {question.options.map((option) => (
                <label key={option.id} className="clarification-option">
                  <input type={question.multiple ? "checkbox" : "radio"} name={name}
                    checked={answer.selected.includes(option.id)}
                    onChange={() => update(index, (current) => ({
                      ...current, unknown: false, other: false,
                      selected: question.multiple
                        ? current.selected.includes(option.id)
                          ? current.selected.filter((id) => id !== option.id)
                          : [...current.selected, option.id]
                        : [option.id],
                    }))} />
                  <span>{option.label}{option.description ? <small>{option.description}</small> : null}</span>
                </label>
              ))}
              <label className="clarification-option">
                <input type={question.multiple ? "checkbox" : "radio"} name={name}
                  checked={answer.unknown}
                  onChange={() => update(index, (current) => ({
                    ...current, selected: [], unknown: !current.unknown, other: false,
                  }))} />
                <span>未知／不确定</span>
              </label>
              <label className="clarification-option">
                <input type={question.multiple ? "checkbox" : "radio"} name={name}
                  checked={answer.other}
                  onChange={() => update(index, (current) => ({
                    ...current, selected: [], unknown: false, other: !current.other,
                  }))} />
                <span>其他／自行填写</span>
              </label>
            </div>
            <label className="clarification-text" htmlFor={name + ":text"}>补充说明</label>
            <textarea id={name + ":text"} rows={2} maxLength={1000} value={answer.text}
              onChange={(event) => {
                const text = event.target.value;
                update(index, (current) => ({ ...current, text }));
              }} />
          </fieldset>;
        })}
        <p className="clarification-note">答案用于核对资料。分析运行仍需单独批准。</p>
        <div className="clarification-actions">
          <button type="submit" disabled={disabled || !ready}>{working ? "正在保存…" : "提交答案"}</button>
          <button type="button" disabled={disabled} onClick={() => void perform(onCancel)}>暂时跳过</button>
        </div>
      </form>
    ) : (
      <>
        {card.answers.map((answer) => {
          const question = card.questions.find((item) => item.field === answer.field);
          return <div className="clarification-answer" key={answer.field}>
            <strong>{question?.title}</strong>
            <p>{answer.unknown ? "未知／不确定" : question?.options
              .filter((option) => answer.selected.includes(option.id)).map((option) => option.label).join("、")}</p>
            {answer.text ? <p>{answer.text}</p> : null}
          </div>;
        })}
        {card.status !== "superseded" ? <button type="button" disabled={disabled}
          onClick={() => void perform(onRevise)}>修改回答</button> : null}
      </>
    )}
    {error ? <p role="alert" className="clarification-error">{error}</p> : null}
  </section>;
}
