# 论文参考的培养形态示意

通过内置 image_gen，参考 Lancaster & Knoblich 2014 图 2，结合图 3 的合格形态说明生成。已检查原始显微图。生成结果是示意图，不是实验照片、标准尺寸或必然出现的唯一形态。灰度用于表现明暗透亮差异，不表示染色。细胞及腔隙细节经示意化处理。

来源：[Generation of cerebral organoids from human pluripotent stem cells](https://www.nature.com/articles/nprot.2014.158)，doi:10.1038/nprot.2014.158。

- [iPSC 集落](ipsc-diagram.png)：参考图 2a 的通用多能干细胞集落形态；原图实际为 hESC，不能称为 iPSC 实测图。
- [胚样体](eb-diagram.png)：图 2b、3a；平滑、致密，外围开始透亮。
- [神经上皮](neural-diagram.png)：图 2c、3c；外围透亮、径向组织。
- [包埋后出芽](budding-diagram.png)：图 2e、3f；扩张的上皮芽，部分有腔隙。
- [脑类器官](organoid-diagram.png)：图 2g；不规则扩张的组织团，避免画成解剖学脑模型。

## 生成提示词

Create ONE original educational schematic of a cerebral organoid culture stage, informed by the supplied scientific figure, NOT a reproduction of the whole figure and NOT a fake micrograph. Use case scientific-educational. White background, grayscale only: gray outlines, restrained light gray tissue with darker gray dense areas. No blue, orange, pink or artificial fluorescent color. Simple flat scientific illustration, morphology recognizable at 60px. No text, panel letter, arrow, scale bar, equipment or background texture. Center one tissue object occupying 75% of a square canvas. Preserve the morphology indicated by the specified reference panel. Do not draw a miniature anatomical brain, smooth toy ball, isolated neurons, or a culture dish.

### ipsc

Reference panel a only: top-view flat adherent pluripotent stem cell colony; one slightly oval patch of densely packed small cells, sharp smooth colony boundary, uniform texture, high nucleus-to-cytoplasm ratio shown as many subtle small gray nuclei. A flat colony, not a 3D grape cluster. Reference panel a is human ESC; use it only as generic pluripotent colony morphology for an iPSC schematic, not as a patient-specific observation.

### eb

Reference panel b (day 5): ONE compact round embryoid body, nearly smooth continuous perimeter, a darker gray dense center and slightly brighter peripheral rim. Fine subtle cell texture, not individually bulging spheres, not a blue cluster. No lumen.

### neural

Reference panel c (day 10), especially the smooth right-side neuroectoderm: ONE smooth oval aggregate with darker dense core, clearly lighter optically translucent peripheral neuroepithelial band. Suggest radial columnar cell organization with sparse short inward strokes inside the rim. No dish, no cavity dominating center, no separate loose cells.

### budding

Reference panel e (day 14): ONE contiguous irregular early organoid with 3-4 broad neuroepithelial buds emerging from a central dense gray mass; each bud has a clear/light peripheral epithelial band, two buds show a small lumen bordered by a substantial tissue wall. The tissue sits inside a barely visible thin outlined transparent Matrigel droplet. Omit migrating cells and spiky non-neural outgrowths shown elsewhere in panel e. Not a uniform sphere in a thick capsule, not bubbles.

### organoid

Reference panel g (day 28): ONE larger asymmetrical cerebral organoid tissue mass, broad irregular lobulated outline with expanded contiguous neuroepithelial regions, optically lighter lobes toward edges and a denser darker gray interior. A few smooth visible internal regional boundaries; no brain-like gyri or paired hemispheres; no many grape-shaped cells; no large empty cyst. A biologically irregular tissue aggregate, not an orange ball.
