declare module "*.css"
declare module "tachyons"
// aos 2.3.4 不带类型声明, 只用到 AOS.init, 手写一条最小声明
declare module "aos" {
  interface AosOptions {
    duration?: number
    easing?: string
    once?: boolean
    offset?: number
    disable?: boolean | string | (() => boolean)
  }
  const AOS: {
    init(options?: AosOptions): void
    refresh(): void
    refreshHard(): void
  }
  export default AOS
}

/** Vite 注入的环境变量。见 frontend/.env.example。 */
interface ImportMetaEnv {
  /** 后端地址。留空则用同源的 /api/v1(开发时由 vite 代理转发)。 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
