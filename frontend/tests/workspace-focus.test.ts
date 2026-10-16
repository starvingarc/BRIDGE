import { workspaceFocus } from "../src/components/WorkspaceFocus";
import type { Session } from "../src/types";

it("follows completed server presentation instead of calling a stopped coordinator paused", () => {
  const session = {status:"idle",input_review_required:false,error:null,uploads:[],artifacts:[],
    assessment:{status:"stopped"},presentation:{stage:"results_ready",summary:"已完成有限解释，缺口仍保留。",
      next_actions:[{id:"view_results",label:"查看已有结果"}]}} as unknown as Session;
  expect(workspaceFocus(session)).toMatchObject({title:"结果已就绪",detail:session.presentation!.summary,target:"overview"});
  expect(workspaceFocus({...session,input_review_required:true}).attention).toBe(true);
});
