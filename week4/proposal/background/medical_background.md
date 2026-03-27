# 急诊科医疗场景 Codex Planning 素材（基于中国急诊规范整理）

> 用途：作为 Codex / LLM 进行医院仿真、急诊 multi-agent 设计、流程建模、系统 brainstorming 的基础材料。\
> 范围：基于以下材料整理，而不是凭空扩展：
>
> 1. 《中国县级医院急诊科建设规范专家共识》
> 2. WS/T 390-2012《医院急诊科规范化流程》
> 3. 市中区人民医院《门诊、急诊就诊流程、注意事项、相关制度》

***

# 1. 文档目标

本文件回答 5 类问题：

1. 急诊科到底是干什么的
2. 什么情况下进入急诊 / 绿色通道
3. 急诊科里有哪些核心 agent
4. 每个 agent 的 `Role / Initialization / Workflow` 是什么
5. 急诊科整体布局、设备配置、与医院其他科室的关系是什么

本文件面向工程实现，因此输出尽量采用“系统视角”而不是论文式叙述。

***

# 2. 急诊科是什么

## 2.1 急诊科定义

急诊科是医院中**独立设置的临床二级学科**，与内科、外科、妇产科等并列。\
它既是提供急诊医疗服务的场所，也是急诊医疗服务体系（EMSS）的重要组成部分，还是突发公共事件医疗救援的核心。

## 2.2 急诊科的核心职责

急诊科主要负责：

- 对**急危重症、创伤患者**进行快速评估、判断、急诊处理、治疗
- 对**慢性病急性发作**进行急诊处理
- 对**人为或环境伤害**进行快速内外科治疗
- 提供**精神心理救助**
- 承担**突发公共卫生事件**和重大事件的医疗保障
- 有条件时承担**院前急救**
- 作为区域急诊急救大平台，联动：
  - 胸痛中心
  - 卒中中心
  - 创伤中心
  - 危重孕产妇救治中心
  - 危重儿童和新生儿救治中心

## 2.3 急诊科服务对象（什么情况下进入急诊）

下列患者应进入急诊体系：

### A. 急危重症

- 心脏骤停
- 呼吸骤停
- 急性冠脉综合征
- 严重心律失常
- 高血压急症 / 危象
- 急性心力衰竭
- 脑卒中
- 癫痫持续状态
- 急性呼吸衰竭
- 重症哮喘
- 咯血
- 急性肾衰竭
- 内分泌危象
- 急性中毒
- 上消化道出血
- 多脏器功能障碍综合征
- 各类休克
- 水电解质 / 酸碱失衡
- 重症感染

### B. 严重创伤和损伤

- 大出血
- 开放性骨折
- 内脏破裂出血
- 颅脑损伤 / 颅内出血
- 高压性气胸
- 气道梗阻
- 创伤失血性休克
- 急腹症
- 电击伤
- 淹溺
- 中暑
- 动物咬伤等

### C. 慢性病急性发作

- 慢性病在短时间内恶化，需急诊处理

### D. 特殊急救场景

- 突发公共事件
- 群体伤亡事件
- 门诊内突然出现需抢救患者
- “三无”危重患者（无姓名、无家属、无治疗经费）

***

# 3. 急诊分级与患者流向

## 3.1 病情严重程度分级（WS/T 390-2012）

### A 级：濒危患者

- 随时可能危及生命
- 例如：
  - 无呼吸
  - 无脉搏
  - 急性意识改变
  - 无反应
  - 需要立即抢救生命的干预

### B 级：危重患者

- 病情可能快速进展为生命危险或致残危险
- 需要尽快安排急诊处理

### C 级：急症患者

- 有急性症状和急诊问题
- 当前尚未明确危及生命
- 但需要在一定时间内安排就诊

### D 级：非急症患者

- 轻症 / 非急症
- 当前没有急性发病情况，或仅有很少不适主诉

> 注：生命体征异常时，病情严重程度应上调一级。

## 3.2 急诊病情分级（工程上可直接用）

- **1级** = A 级濒危患者
- **2级** = B 级危重患者
- **3级** = C 级急症患者，或虽看似轻但需要 `>=2` 项急诊资源
- **4级** = D 级非急症患者，仅需 `0~1` 项急诊资源

## 3.3 分区与分流

### *红区*

*进入对象：*

- *1级患者*
- *2级患者*

*处理特点：*

- *立即支持、抢救、诊疗*
- *靠近复苏室 / 抢救室*
- *配置最强急救资源*

### *黄区*

*进入对象：*

- *3级患者*

*处理特点：*

- *在候诊与观察中完成进一步评估*
- *病情变化时可升级到红区*
- *候诊时间不宜超过 30 分钟*

### *绿区*

*进入对象：*

- *4级患者*

*处理特点：*

- *快速处理*
- *针对轻症 / 资源需求少的患者*
- *可设置快速处理诊室*

***

# 4. 急诊整体流程（系统版）

## 4.1 标准主流程

`患者到达 -> 分诊 -> 分区分流 -> 医师评估 -> 检查/治疗 -> 留观/住院/手术/ICU/出院/转院`

## 4.2 绿色通道流程

`患者到达 -> 分诊护士识别危重 -> 送抢救室 -> 吸氧/监护/静脉通路/病历 -> 首诊医师快速评估 -> 抢救医嘱 + 检查医嘱 + 会诊医嘱 -> 专科会诊 -> 手术/ICU/病房/继续抢救`

## 4.3 门诊内抢救转急诊流程

`门诊发现需抢救患者 -> 门诊医师+护士现场抢救 -> 组织专科会诊 -> 如诊断不明确则继续抢救 -> 情况允许后护送至急诊 -> 门急诊交接`

***

# 5. 急诊科有哪些 Agent

下面按工程建模方式，把急诊科拆成可模拟的 agent。

***

# 5.1 Patient Agent（患者）

## Role

- 表示急诊服务的接受者
- 提供主诉、症状、配合检查与治疗
- 根据病情被分流到不同区域
- 接受诊疗、留观、住院、转院或离院

## Initialization

初始化建议字段：

```yaml
patient_id:
name:
age:
sex:
arrival_mode: [walk-in, family, wheelchair, stretcher, ambulance, transfer]
arrival_time:
chief_complaint:
symptom_onset_time:
vitals:
  temp:
  bp:
  hr:
  rr:
  spo2:
acuity_hint:
special_flags:
  - elderly
  - disabled
  - pregnant
  - child
  - military_priority
  - no_name
  - no_family
  - no_funds
trauma_flag:
time_window_flag:
  - chest_pain
  - stroke
  - trauma
patience:    # 可选，若要模拟 LWBS
consent_status:
payment_status:
```

## Workflow

1. 到达急诊入口
2. 接受分诊
3. 被分配到红 / 黄 / 绿区
4. 接受医师评估
5. 配合检查与治疗
6. 根据病情变化被升级 / 降级
7. 最终去向：
   - 出院
   - 留观
   - 急诊综合病房
   - EICU / ICU
   - 手术室
   - 转院

## 行为特征

- 多数情况下是被动流转
- 通过主诉、病史、疼痛、配合程度影响流程
- 危重患者由医护主导推进
- 若做仿真，可增加：
  - 焦虑
  - 疼痛程度
  - 家属陪同
  - 等待容忍度

***

# 5.2 Triage Nurse Agent（分诊护士）

## Role

- 急诊入口的第一临床筛查者
- 完成分诊、病情分级、分区分流
- 识别需要立即抢救或进入绿色通道的患者

## Initialization

```yaml
agent_type: triage_nurse
experience_years: >=5   # WS/T 390 推荐分诊护士应具有较丰富经验
skills:
  - triage
  - vitals_collection
  - emergency_recognition
  - routing
station:
  - triage_desk
access_to:
  - thermometer
  - blood_pressure_monitor
  - pulse_oximeter
  - triage_form
```

## Workflow

1. 接待来诊患者
2. 登记基础信息：
   - 姓名
   - 性别
   - 年龄
   - 症状
   - 生命体征
   - 住址
   - 来院时间
   - 来院方式
   - 工作单位 / 联系方式等
3. 判断病情严重程度（A/B/C/D）
4. 判断急诊病情分级（1/2/3/4）
5. 分配就诊区域：
   - 红区
   - 黄区
   - 绿区
6. 对可能危及生命者立即送抢救室
7. 对符合绿色通道者立即启动绿色通道

## 输出

```yaml
triage_result:
  severity: [A, B, C, D]
  level: [1, 2, 3, 4]
  zone: [red, yellow, green]
  green_channel: true/false
  routing_destination:
```

***

# 5.3 Emergency Physician Agent（急诊首诊医师 / 急诊医师）

## Role

- 红黄绿各区的核心临床决策者
- 对患者进行快速评估、诊断、开立医嘱、抢救、决定去向
- 在绿色通道中承担首诊责任

## Initialization

```yaml
agent_type: emergency_physician
training:
  - emergency_residency_or_equivalent
experience_years: >=3
skills:
  - primary_assessment
  - emergency_decision
  - airway_management
  - resuscitation
  - order_entry
  - consultation_request
  - disposition
authority:
  - labs
  - imaging
  - meds
  - procedures
  - consults
  - ICU_admission_request
  - OR_request
```

## Workflow

1. 接收分诊信息
2. 问病史、查体
3. 迅速识别威胁生命的主要因素
4. 下达：
   - 抢救医嘱
   - 检查医嘱
   - 急会诊医嘱
   - 药物医嘱
5. 监测病情变化，必要时升级分区
6. 决定去向：
   - 抢救继续
   - 留观
   - 入院
   - ICU
   - 手术
   - 出院
   - 转院

## 关键行为

- 实行首诊负责制
- 不得推诿危重患者
- 危重患者可先救治后补费用
- 所有危重患者诊断、检查、治疗、转运须在医师监护下进行

***

# 5.4 Bedside Nurse / Resuscitation Nurse Agent（床旁护士 / 抢救护士）

## Role

- 执行医嘱
- 监测生命体征
- 抢救室和留观室护理
- 转运与交接支持

## Initialization

```yaml
agent_type: bedside_nurse
skills:
  - monitoring
  - IV_access
  - oxygen_delivery
  - medication_execution
  - charting
  - transfer_support
  - observation
station:
  - resuscitation_room
  - observation_area
  - treatment_area
```

## Workflow

1. 接收医嘱
2. 执行：
   - 吸氧
   - 生命体征监护
   - 建立静脉通路
   - 输液 / 注射 / 抽血 / 协助操作
3. 在留观区定期巡查
4. 发现病情恶化立即上报
5. 协助患者转运到：
   - 检查区
   - 手术室
   - ICU
   - 病房

## 输出

- 护理记录
- 异常事件告警
- 转运完成状态

***

# 5.5 Specialist Physician Agent（专科医师）

## Role

- 参与急会诊
- 提供专科处理意见
- 决定专科收住、手术、后续治疗

## Initialization

```yaml
agent_type: specialist
specialty:
  - cardiology
  - neurology
  - surgery
  - orthopedics
  - obstetrics
  - ent
  - ophthalmology
  - etc
on_call: true
response_time_target: 10min
```

## Workflow

1. 接收急诊会诊通知
2. 在规定时间内到场（绿色通道要求 10 分钟）
3. 快速查体并听取急诊医师病情介绍
4. 给出专科意见
5. 若需住院 / 手术 / ICU，负责进一步接收或转运安排

## 进入场景

- 超出急诊专业授权范围
- 明确时间窗疾病
- 创伤 / 多器官损伤
- 妇产、眼科、耳鼻喉等专科急诊
- 需要手术 / ICU / 专科病房收治

***

# 5.6 Consultation Coordinator Agent（会诊协调 / 医务部 / 总值班）

## Role

- 处理多发伤、多器官病变、重大抢救时的跨科协调
- 召集 MDT
- 决定由哪个专科主接收

## Initialization

```yaml
agent_type: coordinator
authority:
  - activate_MDT
  - resolve_interdepartment_conflict
  - allocate_primary_service
  - escalate_to_hospital_command
```

## Workflow

1. 接到复杂危重症上报
2. 召集相关专业科室人员
3. 组织会诊
4. 根据威胁生命最主要的病种确定主责专科
5. 推动 ICU / 手术室 / 病区接收

***

# 5.7 Registration / Billing Agent（挂号 / 收费 / 行政支持）

## Role

- 负责挂号、收费、住院办理、费用记录
- 对绿色通道患者提供“后补手续”支持

## Initialization

```yaml
agent_type: admin
functions:
  - registration
  - payment
  - admission_processing
  - emergency_green_channel_billing_record
```

## Workflow

1. 普通患者完成挂号 / 收费
2. 绿色通道患者先救治，后记录费用
3. 住院患者办理住院手续
4. 与临床区同步患者身份和费用状态

***

# 5.8 Imaging Agent（影像检查单元）

## Role

- 完成急诊影像检查与急诊报告
- 支持绿色通道优先检查

## Initialization

```yaml
agent_type: imaging_unit
modalities:
  - xray
  - ct
  - ultrasound
  - mri   # 推荐标准/条件允许
target_turnaround:
  xray_ct: 30min
  ultrasound: 15min
```

## Workflow

1. 接收检查申请
2. 优先处理绿色通道患者
3. 输出急诊报告
4. 对危急结果触发回传

***

# 5.9 Lab Agent（检验单元）

## Role

- 完成标本检验与结果回报
- 配合危急值报告制度

## Initialization

```yaml
agent_type: lab_unit
services:
  - CBC
  - urine
  - biochemistry
  - coagulation
  - blood_gas
  - crossmatch
target_turnaround:
  routine: 30min
  biochem_coag: 60min
  crossmatch: 60min
  crossmatch_no_stock: 90min
```

## Workflow

1. 接收标本
2. 优先处理急危重症
3. 输出结果
4. 对危急值回报临床

***

# 5.10 Pharmacy Agent（药学部门）

## Role

- 接收处方并优先发药
- 绿色通道患者优先保障药物可得性

## Initialization

```yaml
agent_type: pharmacy
functions:
  - dispense
  - emergency_med_supply
  - priority_green_channel
```

## Workflow

1. 接收处方
2. 判断是否绿色通道
3. 优先配药发药
4. 同步药品供应状态

***

# 5.11 OR Agent（手术室）

## Role

- 接收急诊手术通知
- 准备手术间、器械、麻醉支持

## Initialization

```yaml
agent_type: operating_room
target_ready_time: 10min
functions:
  - room_preparation
  - equipment_ready
  - notify_staff
  - anesthesia_assessment
```

## Workflow

1. 接收手术通知
2. 10 分钟内准备完毕
3. 通知麻醉及相关人员到场
4. 接收患者并完成急诊手术支持

***

# 5.12 ICU / EICU Agent（重症监护接收单元）

## Role

- 接收危重但已完成初步抢救、需持续重症监护的患者

## Initialization

```yaml
agent_type: EICU
bed_count:
  county_basic: >=6
  county_recommended_or_tertiary: >=12
monitoring:
  - continuous_monitoring
  - ventilator_support
  - blood_gas
  - hemodynamic_support
```

## Workflow

1. 接到急诊接收请求
2. 判断床位和接收条件
3. 接收转运患者
4. 持续监护和进一步治疗

***

# 6. 急诊科整体布局（科室 / 空间）

## 6.1 布局原则

- 急诊科应设置在**一楼**
- 有醒目路标和标识
- 应为**独立功能区**
- 新建 / 改建时应尽量在同一区域内完成就诊、检查、抢救，避免患者在露天或不同楼之间来回穿梭
- 入口应宽敞通畅，适合轮椅、平车、担架
- 应设置无障碍通道
- 与检验、影像、抢救区域之间绿色通道要清晰
- 有条件可分设：
  - 普通急诊入口
  - 危重患者入口
  - 救护车入口
- 承担灾害救援时需具备化学 / 毒物污染患者处置设施

## 6.2 支持区（Support Area）

支持区通常包括：

- 挂号
- 收费
- 候诊
- 急诊检验
- 影像检查
- 急诊药房
- 公共卫生间
- 行政 / 病案支持

要求：

- 抢救患者优先窗口
- 候诊区面积建议 >= 40 平方米

## 6.3 医疗区（Clinical Area）

医疗区至少包括：

- 急诊分诊区 / 分诊台
- 急诊诊治区
- 急诊抢救室
- 复苏室（有条件）
- 急诊创伤处置室
- 急诊留观室
- 急诊综合病房
- EICU
- 急诊治疗室
- 急诊手术室（推荐）
- 隔离室
- 心电图室
- 石膏间
- 创伤处置室
- 检验室
- B 超室
- X 线室
- CT 室
- 急诊药房

## 6.4 分区模型（推荐直接做系统空间图）

```text
ED
├── Entrance
├── Registration/Billing
├── Triage Desk
├── Waiting Area
├── Red Zone
│   ├── Resuscitation Room
│   ├── Shock/Trauma Bay
│   ├── Emergency OR (optional/recommended)
│   └── Fast transfer path to EICU/ICU
├── Yellow Zone
│   ├── Evaluation Rooms
│   ├── Observation Area
│   └── Nurse Station
├── Green Zone
│   ├── Fast Track Clinic
│   └── Minor Treatment Room
├── Imaging
│   ├── X-ray
│   ├── Ultrasound
│   ├── CT
│   └── MRI (recommended / optional)
├── Lab / POCT
├── Pharmacy
├── Emergency Ward
├── EICU
└── Transfer Corridors
```

***

# 7. 关键设备与能力

## 7.1 分诊区设备

- 体温检测
- 血压测量
- 氧饱和度检测

## 7.2 抢救室核心设备

- 多功能抢救床
- 监护仪
- 输液泵、注射泵
- 呼吸机（有创 / 无创 / 转运）
- 简易呼吸器
- 气管插管装置
- 可视喉镜
- 心电图机
- 心脏起搏 / 除颤仪
- 临时起搏器
- 心肺复苏机
- 床旁超声
- 血气生化分析仪
- POCT
- 洗胃机
- 抢救车
- 供氧设备
- 吸引器
- 儿童 / 婴儿急救设备
- 可开展：
  - CPR
  - 除颤
  - 临时起搏
  - 休克复苏
  - 气管插管
  - 机械通气
  - 洗胃
  - 深静脉置管
  - 静脉溶栓
  - 胸腹腔穿刺闭式引流等

## 7.3 EICU 设备

- 每床监护仪
- 每床输液泵 / 微量泵
- 1\~2 张床配 1 台呼吸机
- 无创呼吸机
- 除颤仪
- 临时起搏仪
- 心肺复苏机
- 降温仪
- 肠内营养泵
- 动态血糖监测
- 血气分析
- 纤支镜（条件达到时）
- 血液净化仪
- IABP / ECMO（推荐条件）

## 7.4 急诊旁设备 / 近邻设备

- 急诊超声
- 急诊 X 线
- 急诊 CT
- MRI（推荐）
- 急诊检验
- 药房
- 急诊内镜 / 杂交手术室（条件允许）

## 7.5 时间窗要求（可直接做系统 SLA）

- 专科会诊到场：**10 分钟内**
- X 线 / CT 报告：**30 分钟内**
- 超声报告：**15 分钟内**
- 常规检验：**30 分钟内**
- 生化 / 凝血：**60 分钟内**
- 配血：**60 分钟内**；无库存血 **90 分钟内**
- 手术室准备：**10 分钟内**
- 黄区候诊：**不宜超过 30 分钟**
- 急诊留观：**不宜超过 72 小时**

***

# 8. 与医院其他科室的关系

## 8.1 急诊科不是孤立科室

急诊科是医院内的“急诊急救平台”，与以下系统强耦合：

### 临床专科

- 心内科
- 神经内科 / 神经外科
- 普外科
- 骨科
- 妇产科
- 眼科
- 耳鼻喉科
- 口腔科
- 儿科（通常独立设置）
- 感染科 / 精神科（转院或专科接收场景）

### 医技科室

- 检验科
- 影像科
- 超声科
- 药学部
- 麻醉科
- 输血相关支持

### 住院与重症系统

- ICU / EICU
- 专科病房
- 急诊综合病房
- 手术室

### 医院管理支持

- 医务部
- 护理部
- 后勤
- 信息科
- 保卫
- 病案
- 财务 / 收费

## 8.2 关系模式

### 急诊 -> 专科

触发条件：

- 超出授权范围
- 需专科手术 / 住院
- 需专科会诊

### 急诊 -> ICU / EICU

触发条件：

- 初步抢救后仍需持续重症监护
- 符合 ICU 标准

### 急诊 -> 手术室

触发条件：

- 危重患者需紧急抢救手术
- 创伤控制手术
- 急腹症 / 出血 / 胸腹颅损伤等

### 急诊 -> 病房

触发条件：

- 明确诊断需住院
- 应优先安排住院

### 急诊 -> 120 / 院前系统

触发条件：

- 医院承担院前急救
- 或接收院前预警、实时数据

### 急诊 -> 管理部门

触发条件：

- 多学科会诊
- 群体伤
- 资源冲突
- 急诊安全事件
- 重大公共卫生事件

***

# 9. 决策规则（可直接给 Codex 用）

## 9.1 分诊规则

```text
IF 无呼吸 / 无脉搏 / 急性意识改变 / 无反应
THEN level=1, zone=red, immediate_resuscitation=true
```

```text
IF 病情可能迅速发展为生命危险或致残
THEN level=2, zone=red
```

```text
IF 为急症且需要 >=2 项急诊资源
THEN level=3, zone=yellow
```

```text
IF 为轻症 / 非急症且仅需 0~1 项资源
THEN level=4, zone=green
```

```text
IF 生命体征异常
THEN 病情分级上调一级
```

## 9.2 绿色通道触发规则

```text
IF 短时间内发病且可能在短时间内危及生命
THEN green_channel=true
```

典型病种包括：

- 严重创伤
- AMI
- 急性心衰
- 卒中
- 急性呼衰
- 急性中毒
- 休克
- 严重哮喘持续状态
- 消化道大出血
- 宫外孕大出血 / 产科大出血
- 急腹症
- 三无危重患者

## 9.3 区域升级规则

```text
IF yellow_zone_patient deteriorates
THEN move_to_red_zone
```

```text
IF observation_patient develops critical_signs
THEN move_to_resuscitation_room
```

## 9.4 留观与去向规则

```text
IF diagnosis_uncertain OR waiting_test_results OR disease_may_progress
THEN disposition=observation
```

```text
IF needs_further_inpatient_care
THEN disposition=admission
```

```text
IF initial_resuscitation_done AND still_critical
THEN disposition=EICU_or_ICU
```

```text
IF condition_stable_after_ED_treatment
THEN disposition=discharge
```

```text
IF hospital_cannot_provide_needed_specialized_care
THEN disposition=transfer
```

***

# 10. 可直接给 Codex 的 brainstorm 方向

## 10.1 系统目标

设计一个“急诊科 multi-agent 仿真系统”，模拟：

- 患者到达
- 分诊
- 分区流转
- 医护协作
- 检查排队
- 绿色通道
- 专科会诊
- 床位 / ICU / 手术室资源竞争
- 最终 disposition

## 10.2 建模对象

- 患者流
- 区域流（红黄绿）
- 医护工作流
- 医技周转时间
- 住院和 ICU 接收延迟
- 绿色通道时间窗
- 多学科协作

## 10.3 关键状态变量

- Patient state
- Triage level
- Zone assignment
- Waiting time
- Physician load
- Nurse load
- Imaging queue
- Lab queue
- OR availability
- EICU bed availability
- Ward bed availability
- Consultation turnaround time

## 10.4 关键评价指标

- 到院到分诊时间
- 到院到首诊医师评估时间
- 红区响应时间
- 绿色通道完成时长
- 检查报告返回时长
- 急诊停留时间
- 留观转住院时间
- ICU boarding 时间
- 手术室响应时间
- 危重患者升级是否及时
- 不同分级患者资源占用情况

***

# 11. 建议给 Codex 的具体任务模板

## 任务 A：先搭基础状态机

请实现：

- Patient 状态机
- Zone 状态机
- Disposition 状态机

## 任务 B：再实现 agent 交互

请实现：

- Patient Agent
- Triage Nurse Agent
- Emergency Physician Agent
- Nurse Agent
- Specialist Agent
- Imaging/Lab/OR/ICU 资源代理

## 任务 C：加入规则引擎

请实现：

- 分级规则
- 绿色通道触发规则
- 升级 / 降级规则
- 会诊超时规则
- 检查超时规则
- 留观超时规则

## 任务 D：加入空间布局

请实现：

- Entrance
- Triage
- Red Zone
- Yellow Zone
- Green Zone
- Observation
- Resuscitation
- Imaging
- Lab
- Pharmacy
- EICU
- Ward
- OR

## 任务 E：加入可视化

请实现：

- 患者轨迹
- 区域拥堵热力图
- 医护工作负载图
- 平均等待时间面板
- 绿色通道 KPI 面板

***

# 12. 明确哪些内容是“文件中有”的，哪些是“工程补充”的

## 来自规范文件、可直接视为规则来源

- 急诊科职责范围
- 分诊分级
- 红黄绿分区
- 绿色通道病种与原则
- 支持区 / 医疗区构成
- 抢救室 / EICU / 留观室等布局
- 关键设备清单
- 关键周转时间
- 多学科协作和急会诊机制
- 住院 / ICU / 转院 / 出院规则
- 72h 留观限制
- 先救治后补手续原则

## 为工程建模而补充、但不违背原文的字段

- patient\_id
- patience
- consent\_status
- queue\_length
- workload
- availability
- event logs
- resource state
- agent internal memory

这些属于系统实现字段，不是原文规范条款。

***

# 13. 最简版系统提示词（可直接喂给 Codex）

```text
请基于以下中国急诊规范，设计一个急诊科 multi-agent simulation 系统。

要求：
1. 急诊科是独立临床二级学科，负责急危重症、创伤、慢性病急性发作、突发事件等的快速评估和处理。
2. 患者按 A/B/C/D 严重程度与 1/2/3/4 级分诊，流向红/黄/绿区。
3. 红区处理 1/2级患者，黄区处理 3级患者，绿区处理 4级患者。
4. 急诊绿色通道适用于短时间内发病且可能快速危及生命的患者，包括严重创伤、AMI、卒中、呼衰、休克、急性中毒、大出血、急腹症、三无危重患者等。
5. 核心 agent 至少包括：
   - Patient Agent
   - Triage Nurse Agent
   - Emergency Physician Agent
   - Bedside Nurse Agent
   - Specialist Agent
   - Imaging Agent
   - Lab Agent
   - Pharmacy Agent
   - OR Agent
   - ICU/EICU Agent
   - Registration/Billing Agent
   - Consultation Coordinator Agent
6. 每个 agent 需要定义：
   - Role
   - Initialization
   - Input
   - Output
   - Workflow
   - Decision rules
7. 急诊布局至少包括：
   - 入口
   - 挂号/收费
   - 分诊台
   - 候诊区
   - 红区/抢救室
   - 黄区/诊治区/留观区
   - 绿区/快速处理区
   - 影像区
   - 检验区
   - 药房
   - EICU
   - 急诊综合病房
   - 手术室
8. 关键时限：
   - 会诊 10 分钟内到场
   - X线/CT 30 分钟内报告
   - 超声 15 分钟内报告
   - 常规检验 30 分钟内
   - 生化/凝血 60 分钟内
   - 配血 60~90 分钟
   - 手术室 10 分钟内准备
   - 留观一般不超过 72 小时
9. 请优先实现：
   - 状态机
   - 规则引擎
   - 资源队列
   - 事件驱动工作流
   - 区域流转
   - 可视化监控面板
```

***

# 14. 结论

如果把急诊科看成一个系统，它不是“单一医生给患者看病”，而是一个：

- **入口分流系统**
- **危重症快速响应系统**
- **多学科协作系统**
- **检查与治疗并行系统**
- **床位与资源调度系统**
- **时间窗管理系统**

对于 Codex 来说，最合适的落地方式不是先写 UI，而是先写：

1. `entity schema`
2. `state machine`
3. `rule engine`
4. `resource scheduler`
5. `event bus`
6. `agent behavior templates`

