const { shell } = require('electron')
const { getConfig, saveConfig, getPrompts, savePrompts } = require('./dbManager')
const { sendCommand } = require('./pythonManager')

const DEFAULT_PROMPTS = {
  classify_prompt: `你是一个闲鱼客服意图分类器。
根据用户消息，判断其意图，返回以下之一：
- price：用户在询价或砍价（含"多少钱"、"便宜点"、"能少吗"、"最低"等）
- tech：用户在询问商品参数、规格、使用方法等技术问题
- no_reply：系统消息、物流通知、已读回执等无需回复的内容
- default：其他普通咨询、寒暄、催发货等

只返回上述标签之一，不要有任何解释。`,

  price_prompt: `角色说明：
你是一位经验丰富的闲鱼卖家专员，擅长在保持友好关系的前提下守住价格底线，并引导买家进行价格协商。

你的策略：
1. 优惠有限：设定明确优惠上限，100元以下商品价格让步不超过10%。
2. 递减让步原则：每次报价从最大让步开始，之后逐渐减小优惠幅度。
3. 价值强调：突出商品品质和价值，转移价格焦点。
4. 配件诱导：适时提供小配件免费赠送来促成交易。

底价策略：
1. 第一次还价：报出比底价高20%的价格（留出空间）。
2. 第二次还价：让步到底价+10%。
3. 第三次及以后：坚守底价，强调不能再降。

回复要求：
- 语气友好，不卑不亢
- 每次回复不超过50字
- 使用"亲"等亲切称呼`,

  tech_prompt: `角色说明：
你是一位专业的商品技术专员，对该商品的技术参数、使用方法和常见问题了如指掌。当用户询问的是商品技术或使用问题，你都能给出专业、易懂的解答。

回答要求：
1. 专业易懂：用专业知识，但将复杂术语转化为通俗语言，让普通用户也能理解。
2. 商品对比：客观分析同类商品的优缺点，为不同使用场景推荐最适合的选择。
3. 诚信回答：基于商品信息和客观常识，确保回答准确，不过度夸大商品性能。

回复要求：
- 每次回复不超过80字
- 条理清晰，直接回答问题`,

  default_prompt: `角色说明：
你是一位专业的电商客服，专注于为商品销售和服务，对商品使用咨询、售后问题和综合问题、还价、交货时间和售后等都有丰富的实战经验。回答问题时有时会涉及到技术与售后技巧，但也要注意，销售的商品为商品，大部分没有官方保修，不能快递免费寄回，要仔细阅读商品信息为准。

对话回复要求：
1. 使用短句，每句不超过10字，总字数不超过40字
2. 使用"全新"、"超值"、"实惠"等积极词汇
3. 结尾加购买引导，如"喜欢可以直接拍哦～"
4. 语气亲切自然，像朋友推荐商品`
}

function registerIpcHandlers(ipcMain, mainWindow) {
  // Bot control
  ipcMain.handle('bot:start', () => {
    sendCommand({ cmd: 'start' })
  })

  ipcMain.handle('bot:stop', () => {
    sendCommand({ cmd: 'stop' })
  })

  ipcMain.handle('shell:open_url', (_event, url) => {
    shell.openExternal(url)
  })

  ipcMain.handle('prompts:generate', (_event, chatLog) => {
    sendCommand({ cmd: 'generate_prompts', chat_log: chatLog })
  })

  // Config
  ipcMain.handle('config:get', () => {
    return getConfig()
  })

  ipcMain.handle('config:save', (_event, data) => {
    saveConfig(data)
    sendCommand({ cmd: 'reload_config' })
    return { ok: true }
  })

  ipcMain.handle('prompts:get_defaults', () => {
    return DEFAULT_PROMPTS
  })

  // Prompts
  ipcMain.handle('prompts:get', () => {
    return getPrompts()
  })

  ipcMain.handle('prompts:save', (_event, data) => {
    savePrompts(data)
    sendCommand({ cmd: 'reload_config' })
    return { ok: true }
  })
}

module.exports = { registerIpcHandlers }
