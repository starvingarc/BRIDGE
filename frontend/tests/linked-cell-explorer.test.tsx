import {act, render, screen, fireEvent, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ProductScatter} from '../src/components/ExpressionUMAP';
import LinkedCellExplorer from '../src/components/spatial/LinkedCellExplorer';
const anatomy=vi.hoisted(()=>({create:vi.fn()}));
vi.mock('../src/anatomy/viewer',()=>({createAnatomyViewer:anatomy.create}));

const relation = {product_state_id:'A', spatial_type_id:'X', relation:'same_type', review_state:'reviewed', basis:'Synthetic test'} as const;
const group = (id: string, total: number, matched: string[]) => ({id,total,fraction:total/3,matched_types:matched,
  unmatched_count:matched.length ? 0 : total,relations:matched.length ? [relation] : []});
const context = {kind:'linked_cell_context',version:'1.0',context_id:'v1',state:'available',missing_reasons:[],
  product:{n_observations:3,n_displayed:3,qualified_assignment:false,unknown_count:1,unassigned_counts:{unknown:1},sources:[],
    records:[{record_id:'0',x:0,y:1,cluster:'c1',type_id:'A'}, {record_id:'1',x:1,y:2,cluster:'c1',type_id:'A'},
      {record_id:'2',x:2,y:0,cluster:'c1',type_id:null}],types:[group('A',2,['X'])],
    clusters:[{...group('c1',3,['X']),unmatched_count:1,composition:[{type_id:'A',count:2,fraction:2/3},{type_id:null,count:1,fraction:1/3}]}]},
  reference:{id:'ref',version:'1',stage:'test stage',n_observations:3,types:['X','Y'],model_available:false,
    sections:[{id:'one',label:'捕获一',n_observations:2,kind:'capture'},{id:'two',label:'捕获二',n_observations:1,kind:'capture'}]},
  crosswalk:{version:'1',entries:[relation]}};
const section = {context_id:'v1',id:'one',label:'捕获一',n_observations:2,coordinate_convention:'image_y_down',
  types:['X','Y'],points:[[1,3,0],[2,4,1]],counts:{X:1,Y:1}};
beforeEach(() => {
  anatomy.create.mockImplementation(()=>{throw new Error('WebGL unavailable');});
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({clearRect(){},fillRect(){},beginPath(){},arc(){},fill(){}} as unknown as CanvasRenderingContext2D);
  vi.spyOn(globalThis,'fetch').mockImplementation(async url => Response.json(String(url).includes('/sections/') ? section : context));
});
it('pin_ignores_hover_and_focus_until_explicit_click_or_Escape', async () => {
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  const user=userEvent.setup();
  const a=await screen.findByRole('button',{name:/A · 2/});
  await user.click(a);
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  expect(await screen.findByTestId('spatial-count')).toHaveTextContent('1 / 2');
  fireEvent.mouseEnter(screen.getByRole('button',{name:/未确定分配 · 1/}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  fireEvent.focus(screen.getByRole('button',{name:/未确定分配 · 1/}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  await user.click(screen.getByRole('button',{name:/未确定分配 · 1/}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 未确定分配');
  expect(screen.getByText('空间对应需要明确的类型标签。')).toBeVisible();
  expect(screen.getByTestId('spatial-count')).not.toHaveTextContent('0 /');
  fireEvent.mouseLeave(screen.getByRole('button',{name:/未确定分配 · 1/}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 未确定分配');
  fireEvent.keyDown(screen.getByLabelText('产品与空间参考联动'),{key:'Escape'});
  expect(screen.queryByTestId('linked-selection')).not.toBeInTheDocument();
});
it('mixed_cluster_retains_unmatched_count and zero differs from unmapped', async () => {
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  const user=userEvent.setup();
  await user.selectOptions(await screen.findByLabelText('产品分组方式'),'cluster');
  await user.click(screen.getByRole('button',{name:/c1 · 3/}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('类型对应 2 / 3');
  expect(screen.getByText(/A：2/)).toHaveTextContent('66.67%');
  vi.mocked(fetch).mockResolvedValueOnce(Response.json({...section,id:'two',n_observations:1,points:[[1,1,1]],counts:{X:0,Y:1}}));
  await user.selectOptions(screen.getByLabelText('空间捕获单元'),'two');
  await waitFor(()=>expect(screen.getByTestId('spatial-count')).toHaveTextContent('n=0 / 1'));
});
it('version_change_discards_late_response', async () => {
  let finish!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation(async url => String(url).includes('/sections/')
    ? new Promise<Response>(resolve => {finish=resolve;}) : Response.json(context));
  const view=render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  await screen.findByRole('button',{name:/A · 2/});
  await waitFor(() => expect(finish).toBeDefined());
  vi.mocked(fetch).mockResolvedValue(Response.json({kind:'linked_cell_context',version:'1.0',context_id:'v2',
    state:'unavailable',missing_reasons:['same_view_candidate_assignments_missing']}));
  view.rerender(<LinkedCellExplorer sessionId="s" umapArtifactId="b"/>);
  await screen.findByText('当前产品视图尚无可连接的候选注释。');
  finish(Response.json(section));
  await waitFor(() => expect(screen.queryByTestId('spatial-count')).not.toBeInTheDocument());
});
it('anatomy_failure_keeps_linked_plots_usable', async () => {
  vi.mocked(fetch).mockImplementation(async url => Response.json(String(url).includes('/sections/') ? section
    : {...context,reference:{...context.reference,model_available:true}}));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  expect(await screen.findByText(/3D 模型加载待恢复/)).toBeVisible();
  await userEvent.click(screen.getByRole('button',{name:/A · 2/}));
  expect(screen.getByTestId('spatial-count')).toHaveTextContent('1 / 2');
});

it('group_change_does_not_move_reference_plane', async () => {
  const viewer={load:vi.fn().mockResolvedValue(true),update:vi.fn(),positionCandidate:vi.fn(),dispose:vi.fn()};
  anatomy.create.mockReturnValue(viewer);
  vi.mocked(fetch).mockImplementation(async url => Response.json(String(url).includes('/sections/') ? section
    : {...context,reference:{...context.reference,stage:'CS15',model_available:true,
      plane_hypothesis:{kind:'near_sagittal_model_landmark',offset:.2}}}));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  await waitFor(()=>expect(viewer.positionCandidate).toHaveBeenCalled());
  expect(viewer.positionCandidate).toHaveBeenCalledWith(true,.2);
  await userEvent.click(screen.getByRole('button',{name:/A · 2/}));
  await userEvent.selectOptions(screen.getByLabelText('产品分组方式'),'cluster');
  await userEvent.click(screen.getByRole('button',{name:/c1 · 3/}));
  expect(viewer.positionCandidate).toHaveBeenCalledTimes(1);
  expect(viewer.load).toHaveBeenCalledTimes(1);
});

it('expands_from_narrow_results_and_preserves_pinned_selection', async () => {
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  const user=userEvent.setup();
  await user.click(await screen.findByRole('button',{name:/A · 2/}));
  await user.click(screen.getByRole('button',{name:'放大联动视图'}));
  expect(screen.getByRole('dialog',{name:'放大的产品与空间联动'})).toBeVisible();
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  await user.click(screen.getByRole('button',{name:'收起联动视图'}));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
});

it('missing_mapping_does_not_display_a_zero_spatial_measurement', async () => {
  vi.mocked(fetch).mockImplementation(async url=>Response.json(String(url).includes('/sections/')?section:
    {...context,product:{...context.product,types:[group('A',2,[])]}}));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  await userEvent.click(await screen.findByRole('button',{name:/A · 2/}));
  expect(await screen.findByText('空间对应待确认。')).toBeVisible();
  expect(screen.getByTestId('spatial-count')).toHaveTextContent('n=2');
  expect(screen.getByTestId('spatial-count')).not.toHaveTextContent('0 /');
});


it('boundary_jitter_does_not_flash_between_types_and_repeated_same_hit_does_not_starve_preview', () => {
  vi.useFakeTimers();
  try {
    const hover=vi.fn(),pin=vi.fn();
    const data={...context.product,records:[
      {record_id:'0',x:0,y:0,cluster:'c1',type_id:'A'},
      {record_id:'1',x:.02,y:0,cluster:'c1',type_id:'B'},
      {record_id:'2',x:2,y:2,cluster:'c1',type_id:null}]};
    const view=render(<ProductScatter data={data} activeKey={null} mode="type" palette={{}} onHover={hover} onPin={pin}/>);
    const plot=screen.getByRole('img',{name:/产品 UMAP/});
    vi.spyOn(plot,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:760,height:500} as DOMRect);
    fireEvent.mouseMove(plot,{clientX:170,clientY:460});
    act(()=>vi.advanceTimersByTime(150));
    expect(hover).toHaveBeenLastCalledWith({kind:'type',id:'A'});
    hover.mockClear();
    for(const x of [173,172,173,172,173]) {
      fireEvent.mouseMove(plot,{clientX:x,clientY:460});
      act(()=>vi.advanceTimersByTime(30));
    }
    expect(hover).not.toHaveBeenCalled();
    for(let i=0;i<5;i++) {
      fireEvent.mouseMove(plot,{clientX:174,clientY:460});
      act(()=>vi.advanceTimersByTime(30));
    }
    expect(hover).toHaveBeenCalledTimes(1);
    expect(hover).toHaveBeenLastCalledWith({kind:'type',id:'B'});
    hover.mockClear();
    fireEvent.mouseMove(plot,{clientX:170,clientY:460});
    fireEvent.mouseLeave(plot);
    act(()=>vi.advanceTimersByTime(150));
    expect(hover).toHaveBeenCalledTimes(1);
    expect(hover).toHaveBeenLastCalledWith(null);
    fireEvent.mouseMove(plot,{clientX:170,clientY:460});
    fireEvent.click(plot,{clientX:174,clientY:460});
    expect(pin).toHaveBeenCalledWith({kind:'type',id:'B'});
    hover.mockClear();
    act(()=>vi.advanceTimersByTime(150));
    expect(hover).not.toHaveBeenCalled();
    fireEvent.mouseMove(plot,{clientX:170,clientY:460});
    view.unmount();
    act(()=>vi.advanceTimersByTime(150));
    expect(hover).not.toHaveBeenCalled();
  } finally {vi.useRealTimers();}
});


it('Escape_cancels_a_pending_plot_preview', async () => {
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a"/>);
  await screen.findByRole('button',{name:/A · 2/});
  vi.useFakeTimers();
  try {
    const plot=screen.getByRole('img',{name:/产品 UMAP/});
    vi.spyOn(plot,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:760,height:500} as DOMRect);
    fireEvent.mouseMove(plot,{clientX:170,clientY:250});
    act(()=>vi.advanceTimersByTime(150));
    expect(screen.getByTestId('linked-preview')).toHaveTextContent('A');
    expect(screen.queryByTestId('linked-selection')).not.toBeInTheDocument();
    fireEvent.mouseMove(plot,{clientX:0,clientY:0});
    act(()=>vi.advanceTimersByTime(150));
    expect(screen.queryByTestId('linked-preview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('linked-selection')).not.toBeInTheDocument();
    fireEvent.mouseMove(plot,{clientX:170,clientY:250});
    act(()=>vi.advanceTimersByTime(150));
    fireEvent.mouseMove(plot,{clientX:590,clientY:460});
    fireEvent.keyDown(screen.getByLabelText('产品与空间参考联动'),{key:'Escape'});
    act(()=>vi.advanceTimersByTime(150));
    expect(screen.queryByTestId('linked-preview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('linked-selection')).not.toBeInTheDocument();
  } finally {vi.useRealTimers();}
});


it('composition_bars_share_pin_with_UMAP_and_keep_unknown_and_unavailable_separate', async()=>{
  const product={...context.product,n_observations:4,n_displayed:4,unknown_count:2,unassigned_counts:{unknown:1,unavailable:1},
    types:[{...context.product.types[0],fraction:.5}],records:[...context.product.records,{record_id:'3',x:3,y:3,cluster:'c1',type_id:null,assignment_state:'unavailable'}]};
  vi.mocked(fetch).mockImplementation(async url=>Response.json(String(url).includes('/sections/')?section:{...context,product}));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a" showComposition/>);
  const a=await screen.findByRole('button',{name:'A: 50%, 2 / 4'});
  expect(screen.getByRole('button',{name:'未确定分配: 25%, 1 / 4'})).toBeVisible();
  expect(screen.getByRole('button',{name:'不可用分配: 25%, 1 / 4'})).toBeVisible();
  await userEvent.click(a);
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  expect(screen.getByRole('button',{name:/A · 2/})).toHaveAttribute('aria-pressed','true');
  fireEvent.mouseEnter(screen.getByRole('button',{name:'不可用分配: 25%, 1 / 4'}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 A');
  expect(await screen.findByTestId('spatial-count')).toHaveTextContent('1 / 2');
  await userEvent.click(screen.getByRole('button',{name:'不可用分配: 25%, 1 / 4'}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 不可用分配');
  expect(screen.getByTestId('spatial-count')).not.toHaveTextContent('0 /');
});

const candidateContext=(receipt:string)=>({...context,product:{...context.product,
  sources:[{receipt_sha256:'c'.repeat(64)},{receipt_sha256:receipt}]}});
it('rejects a replacement candidate after the assessment resolver bound the previous receipt',async()=>{
  vi.mocked(fetch).mockResolvedValue(Response.json(candidateContext('b'.repeat(64))));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a" expectedCandidateReceiptSha256={'a'.repeat(64)}
    showComposition fallback={<p>Saved candidate A composition</p>}/>);
  expect(await screen.findByText('细胞注释版本已更新，请重新打开此评估结果。')).toBeVisible();
  expect(screen.getByText('Saved candidate A composition')).toBeVisible();
  expect(screen.queryByLabelText('产品与空间参考联动')).not.toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.some(([url])=>String(url).includes('/sections/'))).toBe(false);
});
it('reload cannot replace the assessment candidate with a new same-view receipt',async()=>{
  let contextReads=0;
  vi.mocked(fetch).mockImplementation(async url=>{
    if(String(url).includes('/sections/'))return new Response('',{status:409});
    return Response.json(candidateContext((++contextReads===1?'a':'b').repeat(64)));
  });
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a" expectedCandidateReceiptSha256={'a'.repeat(64)}
    showComposition fallback={<p>Saved candidate A composition</p>}/>);
  await userEvent.click(await screen.findByRole('button',{name:'重新加载当前版本'}));
  expect(await screen.findByText('细胞注释版本已更新，请重新打开此评估结果。')).toBeVisible();
  expect(screen.getByText('Saved candidate A composition')).toBeVisible();
  expect(screen.queryByLabelText('产品与空间参考联动')).not.toBeInTheDocument();
  expect(contextReads).toBe(2);
});

it('reference subtype mode preserves broad labels and missing states without claiming spatial subtype matches',async()=>{
  const refined={...context,product:{...context.product,
    reference_subtypes:{source_label:'参考表达相似性',single_source:true,resolved_count:1,source_binding:{},
      groups:[group('L2:RG_mFP',1,[]),group('A',1,[])]},
    records:context.product.records.map((r,i)=>({...r,reference_subtype_id:i===0?'L2:RG_mFP':r.type_id}))}};
  vi.mocked(fetch).mockImplementation(async url=>Response.json(String(url).includes('/sections/')?section:refined));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a" showComposition/>);
  const user=userEvent.setup();
  await user.selectOptions(await screen.findByLabelText('产品分组方式'),'subtype');
  await user.click(screen.getByRole('button',{name:'RG mFP: 33.33%, 1 / 3'}));
  expect(screen.getByTestId('linked-selection')).toHaveTextContent('已锁定 RG mFP');
  expect(screen.getByText('空间匹配层级：细胞类型。')).toBeVisible();
  expect(screen.getByTestId('spatial-count')).not.toHaveTextContent('0 /');
  expect(screen.getByRole('button',{name:/未确定分配 · 1/})).toBeVisible();
  await user.click(screen.getByRole('button',{name:'查看类型分布'}));
  expect(screen.queryByRole('button',{name:/RG mFP:/})).not.toBeInTheDocument();
  await user.click(screen.getByRole('button',{name:/A · 2/}));
  expect(screen.getByTestId('spatial-count')).toHaveTextContent('1 / 2');
});
it('keeps internal review narratives out of the expanded source disclosure',async()=>{
  const internal='Codex 展示语义审阅 0.2：开发审阅 1.1.0 的宽转录家族定义';
  vi.mocked(fetch).mockImplementation(async url=>Response.json(String(url).includes('/sections/')?section:
    {...context,reference:{...context.reference,model_attribution:'Synthetic Atlas; display colors adapted',model_license:'CC BY 4.0'},crosswalk:{...context.crosswalk,entries:[{...relation,basis:internal}]}}));
  render(<LinkedCellExplorer sessionId="s" umapArtifactId="a" showComposition/>);
  await userEvent.click(await screen.findByText('数据与来源'));
  expect(screen.getByRole('button',{name:'下载绘图数据'})).toBeVisible();
  expect(screen.queryByText(internal,{exact:false})).not.toBeInTheDocument();
  expect(screen.getByText(/Synthetic Atlas; display colors adapted/)).toHaveTextContent('CC BY 4.0');
  expect(screen.queryByText(/HDBR/)).not.toBeInTheDocument();
  expect(document.querySelector('.figure-panel-letter')).toBeNull();
});
