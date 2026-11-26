# ModelArts课程实验环境

实验主机为Ubuntu 22.04，以普通用户运行项目内安装的程序。KVM不可用，采用QEMU TCG运行x86_64 Linux虚拟机，分配4个虚拟CPU、8192 MiB内存。虚拟磁盘因原镜像导入时空间不足，从16 GiB在线扩展至48 GiB；CPU、内存和Docker实例保持。

Docker 29.1.3只在客机本地监听，通过项目专属SSH连接映射为权限0600的Unix套接字：

`DOCKER_HOST=unix://[server-project]/guest/docker.sock`

任务容器禁用网络，不挂载主机工作区或账号凭据。DSH运行时及公开依赖通过项目卷或docker cp注入。计时求解、原题评分及镜像导入共用`run/work/input-efficiency-20261126/resources/whole-vm.lock`，独占执行。

实际Docker身份、隔离和运行时资格见`run/work/input-efficiency-20261126/execution.json`及其绑定的资格记录。三种语言的Aider镜像及五张SWE镜像已准备，逐题原评分资格见该目录的`preflight/`：原始候选不通过，官方参考候选通过。初期小容器与CPU测试单独保留在根目录的qualification.json、small-image.json、cpu-bootstrap.json；它们用于环境准备，任务成绩以独立原评分记录为准。

模型仅使用hy4flash-free。Mac保留已登录CodeBuddy的最小中继，服务器保存每次真实请求、响应及其自身零积分回执；账号凭据留在Mac。新费用不明或非零立即停止新生成，历史未知单列保留。

`guest_vm.py`、`prepare_host.py`等文件保存实际环境搭建程序。发布副本将项目绝对路径替换为`[server-project]`；在新服务器复用时，将其设为新的项目根目录。普通Linux Docker服务器可直接提供自己的Unix套接字，无需额外虚拟机。冻结模型运行代码、依赖版本及每题输入另随证据包提供。
