import { useEffect, useId, useRef, useState } from "react";
import { matrixName, suggestedContext, suggestedSourceFamily, validSourceFamily } from "./mapping";
import type { MappingInput, MaterialOption, RunInfo } from "./types";

/** Undefined while the declaration is incomplete; null when the researcher chose to attach data without mapping yet. */
export type Declaration = MappingInput | null | undefined;

const LATER = "__later", OTHER = "__other";
const COMMON = ["X", "layers/counts"];
const LAYER = /^[A-Za-z0-9_.-]{1,80}$/;
type CaptureMode = "unknown" | "one" | "column";

/** The capture answer as sent, or undefined while a chosen answer still lacks its name; "unknown" sends nothing. */
function captureOf(mode: CaptureMode, value: string): MappingInput["capture"] | null | undefined {
  const name = value.trim();
  if (mode === "unknown") return null;
  if (!name || name.length > 160) return undefined;
  return mode === "one" ? { id: name } : { column: name };
}

/**
 * What mapping needs to know about attached data, asked in plain words. The matrix list comes from the file itself;
 * which one holds raw counts is always the researcher's choice, never guessed from names or values.
 */
export function DataDeclaration({ run, assay, material, collectedOn, onChange }: {
  run: RunInfo; assay: string; material: MaterialOption | undefined; collectedOn: string | null | undefined; onChange: (value: Declaration) => void;
}) {
  const id = useId();
  const listed = material?.locations;
  const locations = listed ?? COMMON;
  const [location, setLocation] = useState("");
  const [layer, setLayer] = useState("");
  const [context, setContext] = useState<MappingInput["sampleContext"]>(() => suggestedContext(run, collectedOn));
  const [family, setFamily] = useState(() => suggestedSourceFamily(run));
  const [captureMode, setCaptureMode] = useState<CaptureMode>("unknown");
  const [captureName, setCaptureName] = useState("");
  useEffect(() => { setLocation(""); setLayer(""); setCaptureMode("unknown"); setCaptureName(""); }, [material?.id]);
  const matrix = location === OTHER ? (LAYER.test(layer.trim()) ? `layers/${layer.trim()}` : "") : location;
  // Reported only when the answer changes, so a parent re-render with a new callback does not loop.
  const report = useRef(onChange);
  report.current = onChange;
  const capture = captureOf(captureMode, captureName);
  const captureKey = capture ? JSON.stringify(capture) : String(capture);
  useEffect(() => {
    report.current(location === LATER ? null : matrix && validSourceFamily(family.trim()) && capture !== undefined
      ? { matrixLocation: matrix, sampleContext: context, sourceFamily: family.trim(), ...(capture ? { capture } : {}) } : undefined);
  }, [location, matrix, context, family, captureKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const sc = assay === "scRNA-seq";
  return <fieldset className="wb-declare">
    <legend>数据说明</legend>
    <div className="wb-declare-q" role="radiogroup" aria-labelledby={`${id}-counts`}>
      <span id={`${id}-counts`}>原始计数在哪里</span>
      <small className="wb-muted">选未归一化、未取对数的计数（UMI counts）。选错会让映射结果失真，不确定就先不映射。</small>
      {locations.map(l => <label key={l} className="wb-radio"><input type="radio" name={`${id}-loc`} value={l} checked={location === l} onChange={() => setLocation(l)} />{matrixName(l)}</label>)}
      {!listed && <label className="wb-radio"><input type="radio" name={`${id}-loc`} value={OTHER} checked={location === OTHER} onChange={() => setLocation(OTHER)} />其他层
        {location === OTHER && <input className="wb-declare-layer" aria-label="层名" placeholder="层名，如 raw" value={layer} onChange={e => setLayer(e.target.value)} />}</label>}
      <label className="wb-radio"><input type="radio" name={`${id}-loc`} value={LATER} checked={location === LATER} onChange={() => setLocation(LATER)} />不确定，先不映射</label>
      {!listed && material && <small className="wb-muted">服务器没有列出这份文件里的矩阵，以上是常见位置。</small>}
    </div>
    {location !== LATER && <>
      <div className="wb-declare-q">
        <span id={`${id}-ctx`}>取样时</span>
        <span className="wb-seg" role="group" aria-labelledby={`${id}-ctx`}>
          <button type="button" aria-pressed={context === "pre_graft"} onClick={() => setContext("pre_graft")}>移植前</button>
          <button type="button" aria-pressed={context === "post_graft"} onClick={() => setContext("post_graft")}>移植后</button>
        </span>
        {context === "post_graft" ? <small className="wb-muted">移植后的样本要用单核（snRNA）参考，它还没有准备好：数据会先关联，参考就绪后再映射。</small>
          : !sc && <small className="wb-muted">移植前只有单细胞（scRNA）参考，单核数据暂时不能映射。</small>}
      </div>
      <div className="wb-declare-q">
        <label htmlFor={`${id}-family`}>细胞来源</label>
        <input id={`${id}-family`} value={family} onChange={e => setFamily(e.target.value)} aria-invalid={!validSourceFamily(family.trim())} />
        <small className="wb-muted">{validSourceFamily(family.trim()) ? "一般填细胞系。同一来源的参考细胞不会拿来比对自己。" : "只能用英文字母、数字和 _ . : -，以字母或数字开头。"}</small>
      </div>
      <div className="wb-declare-q" role="radiogroup" aria-labelledby={`${id}-capture`}>
        <span id={`${id}-capture`}>捕获批次</span>
        <small className="wb-muted">用于检测双细胞</small>
        <label className="wb-radio"><input type="radio" name={`${id}-cap`} checked={captureMode === "one"} onChange={() => setCaptureMode("one")} />整个文件来自一次捕获</label>
        <label className="wb-radio"><input type="radio" name={`${id}-cap`} checked={captureMode === "column"} onChange={() => setCaptureMode("column")} />文件里有几次捕获，记在一列里</label>
        <label className="wb-radio"><input type="radio" name={`${id}-cap`} checked={captureMode === "unknown"} onChange={() => setCaptureMode("unknown")} />不清楚</label>
        {captureMode !== "unknown" && <input className="wb-declare-layer" value={captureName} onChange={e => setCaptureName(e.target.value)}
          aria-label={captureMode === "one" ? "捕获批次名" : "捕获批次所在的列"} aria-invalid={captureName.trim().length > 160}
          placeholder={captureMode === "one" ? "批次名，如通道号或文库号" : "obs 里的列名"} />}
        {captureMode === "unknown" && <small className="wb-muted">不检测双细胞</small>}
      </div>
      <small className="wb-muted">提交后不能修改，请核对后再提交。</small>
    </>}
  </fieldset>;
}
