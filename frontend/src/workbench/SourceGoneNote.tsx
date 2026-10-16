/** A registered result whose source changed or went missing: the record stays, its numbers do not. */
export function SourceGoneNote({ what }: { what: string }) {
  const subject = /^[A-Za-z]/.test(what) ? ` ${what} ` : what;
  return <div className="wb-muted" role="status"><p>这次{subject}的来源文件已改变或丢失。</p><p>只保留登记信息，见「记录」。</p></div>;
}
