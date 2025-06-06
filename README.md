# 微信流水分析工具
**功能：**

- ✅流水记录导出（基于**取证报告** / **微信支付交易明细证明**）

- ✅大模型对话式数据分析

# 使用方法
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

## 至此，项目所有功能可以正常使用

## 需再次启动项目，运行 `start.bat` 即可
