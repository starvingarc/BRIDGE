import {render,screen,waitFor,act} from '@testing-library/react';
import AssessmentCellExplorer from '../src/components/spatial/AssessmentCellExplorer';
vi.mock('../src/components/spatial/LinkedCellExplorer',()=>({default:({sessionId,umapArtifactId,showComposition,expectedCandidateReceiptSha256}:{sessionId:string;umapArtifactId:string;showComposition:boolean;expectedCandidateReceiptSha256?:string})=><p data-receipt={expectedCandidateReceiptSha256}>Linked {sessionId}/{umapArtifactId} {showComposition?'with composition':''}</p>}));
afterEach(()=>vi.restoreAllMocks());
it('opens only the server-bound same-scope artifact and retains composition on unavailable response',async()=>{
  const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValueOnce(Response.json({state:'available',umap_artifact_id:'bound',binding_token:'token',candidate_receipt_sha256:'a'.repeat(64)}));
  const view=render(<AssessmentCellExplorer sessionId="s" scopeDigest="scope" evidenceAlias="E-candidate" fallback={<p>Saved composition</p>}/>);
  expect(await screen.findByText('Linked s/bound with composition')).toHaveAttribute('data-receipt','a'.repeat(64));
  expect(fetcher).toHaveBeenCalledWith('/api/sessions/s/assessment/cell-explorer?scope_digest=scope&evidence_alias=E-candidate',expect.objectContaining({credentials:'same-origin'}));
  fetcher.mockResolvedValueOnce(Response.json({state:'unavailable',reason_code:'ambiguous'}));
  view.rerender(<AssessmentCellExplorer sessionId="s" scopeDigest="new-scope" evidenceAlias="E-candidate" fallback={<p>Saved composition</p>}/>);
  expect(await screen.findByText('细胞表达谱与空间参考暂不可用。')).toBeVisible();
  expect(screen.getByText('Saved composition')).toBeVisible();
  expect(screen.queryByText(/Linked s\/bound/)).not.toBeInTheDocument();
});
it('a late resolver response cannot replace a new scope',async()=>{
  let finish!:(response:Response)=>void;
  vi.spyOn(globalThis,'fetch').mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}))
    .mockResolvedValueOnce(Response.json({state:'available',umap_artifact_id:'new',binding_token:'token-new',candidate_receipt_sha256:'b'.repeat(64)}));
  const view=render(<AssessmentCellExplorer sessionId="s" scopeDigest="old-scope" evidenceAlias="E-old" fallback={<p>Saved composition</p>}/>);
  await waitFor(()=>expect(finish).toBeDefined());
  view.rerender(<AssessmentCellExplorer sessionId="s" scopeDigest="new-scope" evidenceAlias="E-new" fallback={<p>Saved composition</p>}/>);
  expect(await screen.findByText('Linked s/new with composition')).toBeVisible();
  await act(async()=>finish(Response.json({state:'available',umap_artifact_id:'old',binding_token:'token-old',candidate_receipt_sha256:'a'.repeat(64)})));
  expect(screen.queryByText(/Linked s\/old/)).not.toBeInTheDocument();
  expect(screen.getByText('Linked s/new with composition')).toBeVisible();
});

it('fails closed when the resolver omits the candidate receipt binding',async()=>{
  vi.spyOn(globalThis,'fetch').mockResolvedValue(Response.json({state:'available',umap_artifact_id:'bound',binding_token:'token'}));
  render(<AssessmentCellExplorer sessionId="s" scopeDigest="scope" evidenceAlias="E-candidate" fallback={<p>Saved composition</p>}/>);
  expect(await screen.findByText('细胞表达谱与空间参考暂不可用。')).toBeVisible();
  expect(screen.getByText('Saved composition')).toBeVisible();
  expect(screen.queryByText(/Linked/)).not.toBeInTheDocument();
});
