import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ChannelsPage } from './page'


const api = vi.hoisted(() => ({
  apply: vi.fn(),
  cancel: vi.fn(),
  getPlatforms: vi.fn(),
  getStatus: vi.fn(),
  notify: vi.fn(),
  notifyError: vi.fn(),
  start: vi.fn()
}))

vi.mock('@hermes/plugin-sdk', async importOriginal => {
  const actual = await importOriginal<typeof import('@hermes/plugin-sdk')>()
  return {
    ...actual,
    applyMessagingOnboarding: api.apply,
    cancelMessagingOnboarding: api.cancel,
    getMessagingOnboardingStatus: api.getStatus,
    getMessagingPlatforms: api.getPlatforms,
    host: { notify: api.notify, notifyError: api.notifyError },
    startMessagingOnboarding: api.start
  }
})

const platforms = [
  {
    id: 'dingtalk',
    name: 'DingTalk',
    description: 'DingTalk',
    enabled: false,
    configured: false,
    state: 'not_configured'
  },
  {
    id: 'weixin',
    name: 'Weixin',
    description: 'Weixin',
    enabled: true,
    configured: true,
    state: 'connected'
  },
  {
    id: 'qqbot',
    name: 'QQ Bot',
    description: 'QQ Bot',
    enabled: false,
    configured: false,
    state: 'not_configured'
  },
  {
    id: 'telegram',
    name: 'Telegram',
    description: 'Telegram',
    enabled: true,
    configured: true,
    state: 'connected'
  }
]

describe('channels page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getPlatforms.mockResolvedValue({ platforms })
    api.cancel.mockResolvedValue({ success: true })
  })

  afterEach(() => cleanup())

  it('shows only the three supported QR channels in product order', async () => {
    render(<ChannelsPage openExternal={vi.fn(async () => true)} />)

    expect(await screen.findByRole('heading', { name: '钉钉' })).toBeTruthy()
    const headings = screen.getAllByRole('heading', { level: 3 }).map(node => node.textContent)
    expect(headings).toEqual(['钉钉', '个人微信', 'QQ'])
    expect(screen.queryByText('Telegram')).toBeNull()
  })

  it('starts a QR session and cancels it when the dialog closes', async () => {
    api.start.mockResolvedValue({
      platform: 'dingtalk',
      pairing_id: 'pairing-1',
      status: 'waiting',
      qr_data_url: 'data:image/png;base64,AA==',
      qr_payload: 'https://example.test/pairing-1'
    })
    render(<ChannelsPage openExternal={vi.fn(async () => true)} />)

    fireEvent.click(await screen.findByRole('button', { name: '钉钉扫码绑定' }))
    expect(await screen.findByRole('img', { name: '钉钉二维码' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '关闭' }))

    await waitFor(() => expect(api.cancel).toHaveBeenCalledWith('dingtalk', 'pairing-1'))
  })

  it('applies a connected session and refreshes platform state', async () => {
    api.start.mockResolvedValue({
      platform: 'qqbot',
      pairing_id: 'pairing-2',
      status: 'connected'
    })
    api.apply.mockResolvedValue({ restart_started: false })
    render(<ChannelsPage openExternal={vi.fn(async () => true)} />)

    fireEvent.click(await screen.findByRole('button', { name: 'QQ扫码绑定' }))

    await waitFor(() => expect(api.apply).toHaveBeenCalledWith('qqbot', 'pairing-2'))
    await waitFor(() => expect(api.getPlatforms).toHaveBeenCalledTimes(2))
    expect(api.notify).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'success', title: 'QQ 已绑定' })
    )
  })
})
