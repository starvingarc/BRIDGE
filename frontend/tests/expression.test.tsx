import {render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {useState} from "react";
import ExpressionOptions from "../src/components/ExpressionOptions";
import ExpressionUMAP, {parseUMAP} from "../src/components/ExpressionUMAP";
import type {ExpressionAnalysis} from "../src/types";

const data = {schema_ref: "bridge://schemas/expression-plot-data/v0.1", kind:"umap", n_observations: 10,
  records:[{record_id:"0",x:1,y:2,group:"A"},{record_id:"1",x:3,y:4,group:"B"}],
  colors:{"分群":["A","B"],"基因 · gene-0":[null,5]}, composition:[
    {group:"A",count:6,fraction:.6},{group:"B",count:4,fraction:.4}]};
it("keeps full denominators and null colors while rejecting misaligned coordinates", () => {
  expect(parseUMAP(data)?.n_observations).toBe(10);
  expect(parseUMAP({...data, colors:{gene:[1]}})).toBeNull();
  expect(parseUMAP({...data, n_observations:11})).toBeNull();
  expect(parseUMAP({...data, records:[data.records[0], data.records[0]]})).toBeNull();
});
it("lets a user type multiple genes and declare both comparison scopes", async () => {
  function Form() {
    const [value,setValue]=useState<ExpressionAnalysis>({});
    return <><ExpressionOptions value={value} disabled={false} onChange={setValue}/><output>{JSON.stringify(value)}</output></>;
  }
  render(<Form/>);
  const user=userEvent.setup();
  await user.type(screen.getByLabelText("表达着色基因（逗号分隔）"),"TH, DDC");
  expect(screen.getByRole("status")).toHaveTextContent('"genes":["TH","DDC"]');
  await user.click(screen.getByLabelText("同时比较同一细胞类型内的两组条件"));
  await user.type(screen.getByLabelText("独立样本列"),"sample");
  expect(screen.getByRole("status")).toHaveTextContent('"sample_key":"sample"');
  expect(screen.getByLabelText(/我确认样本代表/)).not.toBeChecked();
});
it("filters displayed points without changing full counts and supports gene coloring", async () => {
  vi.spyOn(HTMLCanvasElement.prototype,"getContext").mockReturnValue({clearRect(){},beginPath(){},arc(){},fill(){}} as unknown as CanvasRenderingContext2D);
  vi.spyOn(globalThis,"fetch").mockResolvedValue(Response.json(data));
  render(<ExpressionUMAP url="/api/sessions/s/artifacts/a"/>);
  const user=userEvent.setup();
  await user.selectOptions(await screen.findByLabelText("查看分群"),"A");
  expect(screen.getByText(/当前显示 1 个点/)).toHaveTextContent("所选范围共 6 个细胞，完整数据共 10 个细胞");
  await user.selectOptions(screen.getByLabelText("着色"),"基因 · gene-0");
  expect(screen.getByText(/色标：蓝/)).toHaveTextContent("灰色为缺失");
});
