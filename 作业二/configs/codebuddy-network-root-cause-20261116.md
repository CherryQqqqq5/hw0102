# CodeBuddy网络故障的根因核验与工程修复

本轮只进行源码检查、真实网络连接对照和已保存失败的回放，模型调用为0。已修复课程适配器删除代理变量的行为，以及空输出被笼统归为非JavaScript Object Notation（JSON，JavaScript对象表示法）的诊断问题；当前正式评测继续停止，原始缺失计费回执保持未知。

## 可重复的故障链

Wi-Fi当前配置中，同一个校园网DNS（Domain Name System，域名系统）地址排在前面且重复六次。直接向该解析器查询CodeBuddy服务域名，在2秒期限内超时；三个公开解析器均返回有效地址。Node系统查询首轮耗时3.525秒，之后七次缓存查询约1至5毫秒，表明单次成功检查容易受缓存影响。

原课程适配器在创建CodeBuddy子进程时删除HTTP_PROXY、HTTPS_PROXY、ALL_PROXY及其小写形式，保留NO_PROXY。本机已配置的本地代理因此不能直接作为该进程的显式代理输入。

实际评测路径是工程内固定的CodeBuddy 2.179.3，检查对象为其codebuddy-headless.js。ProxyResolver按配置文件、环境、操作系统的顺序选择代理；系统代理探测限制为2秒。HttpProxyInterceptor允许system来源在连接错误后自动转直连，并另有系统代理证书错误后的行为。因而删除显式代理会使请求依赖自动探测及其回退路径。

对同一主机交错执行五轮无认证HTTP（Hypertext Transfer Protocol，超文本传输协议）HEAD请求，只改变子进程代理环境；连接上限3秒，总上限6秒：

| 环境 | 成功连接 | 解析阶段超时 | 总耗时 |
|---|---:|---:|---|
| 原适配器：代理变量被删除 | 3/5 | 2/5 | 0.256至3.006秒；一次成功查询的解析本身耗时2.273秒 |
| 修复后：继承已有本地代理 | 5/5 | 0/5 | 0.181至0.187秒 |

五次修复后连接的对端均为本地代理，服务返回404，确认到达目标HTTP主机；该状态不用于判断模型服务或计费。完整实测见codebuddy-network-route-check-20261116.json。

这些结果支持当前机器存在不稳定的直连解析路径，而删除代理扩大了课程进程对该路径的依赖。原始故障没有保留DNS报文或每个HTTP阶段的调试日志，无法进一步还原事故当刻使用了哪台递归解析器、是否先经历系统代理探测失败或回退；不将该缺口写成已证明的唯一历史原因。

Node官方说明dns.lookup调用操作系统的getaddrinfo，而dns.resolve直接发起DNS查询；因此两类查询的结果与耗时可能不同。本轮同时检查两类路径。[Node 23.11.0实现说明](https://nodejs.org/download/release/v23.11.0/docs/api/dns.html#implementation-considerations)

## 已完成修复

1. CodeBuddy子进程保留现有代理和绕过列表，继续过滤原有的无关Application Programming Interface（API，应用程序编程接口）密钥；未修改全局代理或Wi-Fi DNS。
2. 免费模式设置CODEBUDDY_DISABLE_PROXY_CONFIG_FILE=1，避免独立的全局代理配置覆盖本次显式环境；移除WORKBUDDY_PROXY_SOURCE继承值，使该客户端按env来源处理现有代理，避免进入system来源的自动转直连分支。变量行为已从固定2.179.3源码核对。
3. 保持免费主、轻、强型号、4096上限、零额外重试及原证书信任设置。
4. 遇到空标准输出并有getaddrinfo ENOTFOUND时，明确记录dns_resolution及billing_status=unknown并致命停止；退出码0不作成功依据。其他进程失败和无效JSON分别记录原因。导出保留故障类别及费用未知字段。
5. 请求记录增加代理环境是否配置、代理配置文件是否禁用两个布尔字段，避免未来仅凭退出码和错误文本猜测运行环境；不记录代理凭据或绕过列表。

## 验证与边界

新增两个回归均先失败后通过：真实子进程环境丢失代理的检查，以及真实v5退出码0、空输出、DNS错误原件的回放。回放明确验证只产生request_error，不产生计费通过事件；脱敏后费用未知字段仍在。完整14项回归通过，实际模型计费校验器codebuddy_free.py与原冻结版本逐字节摘要一致。

验证命令：

```sh
source work/course-hy4flash-env.sh
work/.venv/bin/python -m course_eval.check_codebuddy_free
work/.venv/bin/python work/check_codebuddy_network_route.py
```

第二条只使用保存的真实响应及进程原件回放、实际本地子进程；第三条只发起10次无认证HEAD请求。均不请求模型。

代码位于course_eval/agent.py、export_revision.py和check_codebuddy_free.py。新代码属于网络修复版本，尚未冻结或运行新的正式矩阵；原v5对应32b5ef1，七条原评分和八次尝试保持。网络连接对照通过不结清此前缺失回执的费用，也不证明未来网络永不失败。模型端到端未重新调用，已返回零积分、未知费用以及原题成绩继续分别记录。
