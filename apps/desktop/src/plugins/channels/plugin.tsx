/**
 * IM Channels — a focused desktop plugin for scan-based IM account binding.
 *
 * The page is intentionally small: it contributes a sidebar route and renders
 * only DingTalk, personal Weixin, and QQ Bot. The scan flow uses the shared
 * messaging onboarding API so the platform credentials still land in Hermes'
 * normal gateway config.
 */

import type { HermesPlugin, RouteContribution, SidebarNavContribution } from '@hermes/plugin-sdk'
import { ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'

import { ChannelsPage } from './page'

const plugin: HermesPlugin = {
  id: 'channels',
  name: 'IM频道',
  description: '扫码绑定钉钉、个人微信和 QQ 消息渠道。',
  defaultEnabled: true,
  register(ctx) {
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: '/channels' } satisfies RouteContribution,
        render: () => <ChannelsPage openExternal={ctx.os.openExternal} />
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 32,
        data: { codicon: 'comment-discussion', label: 'IM频道', path: '/channels' } satisfies SidebarNavContribution
      }
    ])
  }
}

export default plugin
