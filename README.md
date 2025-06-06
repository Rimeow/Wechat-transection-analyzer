![banner](https://github.com/user-attachments/assets/0906c485-579a-42e9-a0a7-43e4cfe12cee)

# 简易导出微信流水数据 + 大模型对话数据分析
**功能：**

- ✅流水记录导出（基于**取证报告** / **微信支付交易明细证明**）

- ✅大模型对话式数据分析（目前支持DeepSeek接口调用/ollama本地模型）

# 1. 本地部署
<details>
<summary>点击展开</summary>

### 一、下载代码

- 方法一：使用 Git 克隆（推荐）

   - 确保你的电脑已安装 Git
   - 检查是否安装：在终端/命令行输入 `git --version`
   - 如果未安装，请从 [Git 官网](https://git-scm.com/) 下载安装

   - 克隆仓库到本地
     ```bash
     git clone https://github.com/Rimeow/Wechat-transection-analyzer.git
     ```
     
     或者使用 SSH 方式：

     ```bash
     git clone git@github.com:Rimeow/Wechat-transection-analyzer.git
     ```

     进入项目目录

     ```bash
     cd Wechat-transection-analyzer
     ```
- 方法二：直接下载 ZIP
    - 访问[项目页面](https://github.com/Rimeow/Wechat-transection-analyzer)
    - 点击绿色的 "Code" 按钮
    - 选择 "Download ZIP"
    - 解压下载的 ZIP 文件到你的工作目录

### 二、安装Python环境

- 使用 `python --version` 验证python环境
  
    - 未配置python环境，请访问 [Python 官网](https://www.python.org/downloads/)下载页面

### 三、运行 `install.bat`

- 成功运行如下图

<img width="524" alt="installbat" src="https://github.com/user-attachments/assets/d9e0a7ca-ebfd-4fad-a458-e16f784ea045" />

- 此脚本实现创建虚拟环境及相关依赖库安装

- **脚本执行完成后按任意键退出即可**

### 四、运行 `start.bat`

- 成功运行如下图（暂未配置DeepSeek API密钥）

<img width="524" alt="start" src="https://github.com/user-attachments/assets/4675cb53-f8b6-442e-9a99-8e9356ebbb23" />

- 在浏览器中输入IP地址，可以访问项目界面

<img width="700" alt="index" src="https://github.com/user-attachments/assets/39f70d10-6a94-4574-adc4-37978db0d6d0" />


### 五、配置 `.env` 文件

- 使用记事本打开 `.env` 文件，可以看到以下参数：
  
  -`DEEPSEEK_API_KEY`：DeepSeek API密钥

  -`OLLAMA_HOST`: 本地ollama地址

  -`OLLAMA_DEFAULT_MODEL`: ollama默认使用模型

  -`SAMPLE_DATA_ROWS`: 发送给大模型的表格行数（**建议设置合理数量以避免超过模型token限制**）

  例：
  ```.env
  DEEPSEEK_API_KEY=sk-9999ce9999d9999bf999c9999d9999
  
  OLLAMA_HOST=http://127.0.0.1:11434
  
  OLLAMA_DEFAULT_MODEL=deepseek-r1:32b
  
  SAMPLE_DATA_ROWS=100
  ```

- 至此，项目所有功能可以正常使用

- 需再次启动项目，运行 `start.bat` 即可
</details>

# 2. 使用方法
<details>
<summary>点击展开</summary>

- 进入工具主页面，可以上传 **报告文件（.zip）** 或 **微信支付交易明细证明（.pdf）**

  <img width="400" alt="界面1" src="https://github.com/user-attachments/assets/3baf478e-791d-4f82-b1e4-a24e6daf34d5" /><img width="400" alt="界面2" src="https://github.com/user-attachments/assets/43923ccf-6a78-4019-afe3-ce01cdc7cb0a" />

- 上传标准格式文件后进入处理页面 处理完成后可以**返回主页面**或**浏览文件**

  <img width="400" alt="处理1" src="https://github.com/user-attachments/assets/73d4c4d1-e7ef-47fe-8b53-e453ad5291ef" /><img width="400" alt="处理完成" src="https://github.com/user-attachments/assets/d7a09a69-78c0-4d70-8866-935021672d70" />

- 左侧可以看到**历史分析报告**
  
  - 🟥红色背景表示 **微信支付交易明细证明（.pdf）** 生成的表格

  - 🟦蓝色背景表示 **报告文件（.zip）** 生成的表格

  <img width="400" alt="界面3" src="https://github.com/user-attachments/assets/07e54892-2afb-4741-9c92-272bfe2e13a6" />

  - 点击⬇️按钮可以下载表格

  - 点击🔍️按钮进入数据分析界面

- 点击要分析的表格右侧🔍️按钮进入**数据分析界面**

  - 右侧对话窗口可以与大模型进行对话，发送的数据行数可通过 `.env` 文件的 `SAMPLE_DATA_ROWS` 设置
  
  <img width="400" alt="对话" src="https://github.com/user-attachments/assets/a33ae238-5726-4b23-84c1-c48226d95e63" />
</details>

# ⚠️重要⚠️ 

标准上传文件：**微信支付交易明细证明（.pdf）** / **报告文件（.zip）**

- **微信支付交易明细证明（.pdf）**
  
   - 在微信中导出的交易明细（附有公章）

    <img width="300" alt="对话" src="https://github.com/user-attachments/assets/c413c113-28c7-43d7-9993-8de7709fa461" />

- **报告文件（.zip）**
  
   - 使用取证软件导出的取证报告（压缩包内包含报告html文件）
 
    <img width="500" alt="对话" src="https://github.com/user-attachments/assets/b5242cfb-13c6-4af9-9424-5c786a14c7e3" />


# 效果演示
<details>
<summary>点击展开</summary>
</details>
