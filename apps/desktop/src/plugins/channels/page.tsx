import {
  applyMessagingOnboarding,
  Button,
  cancelMessagingOnboarding,
  cn,
  Codicon,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  getMessagingOnboardingStatus,
  getMessagingPlatforms,
  host,
  icons,
  Loader,
  type MessagingOnboardingSession,
  type MessagingPlatformInfo,
  startMessagingOnboarding,
  StatusDot,
  type StatusTone,
  Tip
} from '@hermes/plugin-sdk'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const { CheckCircle2, ExternalLink, Loader2, Plus, RefreshCw } = icons

const IM_PLATFORM_IDS = ['dingtalk', 'weixin', 'qqbot'] as const
type ImPlatformId = (typeof IM_PLATFORM_IDS)[number]

const CHANNEL_COPY: Record<ImPlatformId, { title: string; description: string; scanHint: string }> = {
  dingtalk: {
    title: '钉钉',
    description: '通过扫码授权自动写入 Client ID 和 Client Secret，连接钉钉机器人消息。',
    scanHint: '请使用钉钉扫码并确认授权。'
  },
  weixin: {
    title: '个人微信',
    description: '通过腾讯 iLink Bot API 扫码登录个人微信，保存账号凭据后接入消息。',
    scanHint: '请使用个人微信扫码，并在手机上确认登录。'
  },
  qqbot: {
    title: 'QQ',
    description: '通过 QQ 开放平台扫码绑定机器人应用，自动写入 App ID 和 Client Secret。',
    scanHint: '请使用 QQ 扫码完成机器人绑定。'
  }
}

const statusText: Record<string, string> = {
  cancelled: '已取消',
  connected: '扫码成功',
  disabled: '已禁用',
  error: '失败',
  expired: '已过期',
  gateway_stopped: '网关未运行',
  not_configured: '未绑定',
  pending_restart: '待重启',
  scanned: '已扫码，等待确认',
  startup_failed: '启动失败',
  waiting: '等待扫码'
}

function platformTone(platform: MessagingPlatformInfo): StatusTone {
  if (!platform.enabled) {
    return 'muted'
  }

  if (platform.configured || platform.state === 'connected') {
    return 'good'
  }

  if (platform.state === 'fatal' || platform.state === 'startup_failed') {
    return 'bad'
  }

  return 'warn'
}

function sessionMessage(session: MessagingOnboardingSession | null): string {
  if (!session) {
    return '正在创建扫码会话...'
  }

  if (session.status === 'connected') {
    return '扫码已完成，正在保存配置...'
  }

  return statusText[session.status] || session.status
}

export function ChannelsPage({ openExternal }: { openExternal: (url: string) => Promise<boolean> }) {
  const [platforms, setPlatforms] = useState<MessagingPlatformInfo[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [activePlatform, setActivePlatform] = useState<MessagingPlatformInfo | null>(null)
  const [onboarding, setOnboarding] = useState<MessagingOnboardingSession | null>(null)
  const [starting, setStarting] = useState(false)
  const [saving, setSaving] = useState(false)
  const appliedRef = useRef<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await getMessagingPlatforms()
      setPlatforms(result.platforms.filter(platform => IM_PLATFORM_IDS.includes(platform.id as ImPlatformId)))
    } catch (error) {
      host.notifyError(error, '加载 IM 频道失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const sortedPlatforms = useMemo(() => {
    const byId = new Map((platforms ?? []).map(platform => [platform.id, platform]))

    return IM_PLATFORM_IDS.map(id => byId.get(id)).filter(Boolean) as MessagingPlatformInfo[]
  }, [platforms])

  const closeDialog = useCallback(() => {
    const current = onboarding
    setActivePlatform(null)
    setOnboarding(null)
    setSaving(false)
    appliedRef.current = null

    if (current && !['connected', 'error', 'expired', 'cancelled'].includes(current.status)) {
      void cancelMessagingOnboarding(current.platform, current.pairing_id).catch(() => undefined)
    }
  }, [onboarding])

  async function begin(platform: MessagingPlatformInfo) {
    setActivePlatform(platform)
    setOnboarding(null)
    setStarting(true)
    setSaving(false)
    appliedRef.current = null

    try {
      const session = await startMessagingOnboarding(platform.id)
      setOnboarding(session)
    } catch (error) {
      host.notifyError(error, `无法启动 ${displayTitle(platform)} 扫码绑定`)
      setActivePlatform(null)
    } finally {
      setStarting(false)
    }
  }

  // eslint-disable-next-line no-restricted-syntax -- idempotency guard for one connected onboarding session.
  useEffect(() => {
    if (!onboarding || !activePlatform || ['error', 'expired', 'cancelled'].includes(onboarding.status)) {
      return
    }

    if (onboarding.status === 'connected') {
      if (appliedRef.current === onboarding.pairing_id) {
        return
      }

      appliedRef.current = onboarding.pairing_id
      setSaving(true)
      void applyMessagingOnboarding(activePlatform.id, onboarding.pairing_id)
        .then(result => {
          host.notify({
            kind: 'success',
            title: `${displayTitle(activePlatform)} 已绑定`,
            message: result.restart_started ? 'Hermes 正在重启消息网关。' : '配置已保存，请手动重启消息网关。'
          })
          setActivePlatform(null)
          setOnboarding(null)
          void refresh()
        })
        .catch(error => {
          appliedRef.current = null
          host.notifyError(error, `保存 ${displayTitle(activePlatform)} 配置失败`)
        })
        .finally(() => setSaving(false))

      return
    }

    const id = window.setTimeout(() => {
      void getMessagingOnboardingStatus(activePlatform.id, onboarding.pairing_id)
        .then(setOnboarding)
        .catch(error => {
          host.notifyError(error, `刷新 ${displayTitle(activePlatform)} 扫码状态失败`)
          setOnboarding(current => (current ? { ...current, status: 'error', error: String(error) } : current))
        })
    }, onboarding.status === 'scanned' ? 1000 : 1800)

    return () => window.clearTimeout(id)
  }, [activePlatform, onboarding, refresh])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader label="正在加载 IM 频道..." type="lemniscate-bloom" />
      </div>
    )
  }

  return (
    <section className="flex h-full min-h-0 flex-col overflow-auto bg-(--ui-workspace-background) px-8 py-7">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">IM频道</h2>
            <p className="mt-1 text-sm text-(--ui-text-tertiary)">扫码绑定常用即时通讯渠道。</p>
          </div>
          <Button onClick={() => void refresh()} size="sm" variant="secondary">
            <RefreshCw className="size-4" />
            刷新
          </Button>
        </header>

        {sortedPlatforms.length === 0 ? (
          <InlineError>当前后端没有返回钉钉、个人微信或 QQ 渠道。请确认 Hermes 已更新到包含这些消息平台的版本。</InlineError>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {sortedPlatforms.map(platform => (
              <ChannelCard key={platform.id} onBind={() => void begin(platform)} platform={platform} />
            ))}
          </div>
        )}
      </div>

      <OnboardingDialog
        onboarding={onboarding}
        onClose={closeDialog}
        open={Boolean(activePlatform)}
        openExternal={openExternal}
        platform={activePlatform}
        saving={saving}
        starting={starting}
      />
    </section>
  )
}

function displayTitle(platform: Pick<MessagingPlatformInfo, 'id' | 'name'>): string {
  return CHANNEL_COPY[platform.id as ImPlatformId]?.title || platform.name
}

function ChannelCard({ onBind, platform }: { onBind: () => void; platform: MessagingPlatformInfo }) {
  const tone = platformTone(platform)
  const title = displayTitle(platform)
  const copy = CHANNEL_COPY[platform.id as ImPlatformId]
  const bound = platform.configured

  return (
    <article className="flex min-h-[8.25rem] items-start gap-4 rounded-lg border border-(--stroke-nous) bg-(--ui-chat-bubble-background) p-5 shadow-sm">
      <ChannelAvatar platform={platform.id as ImPlatformId} title={title} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-lg font-semibold">{title}</h3>
          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            <StatusDot tone={tone} />
            {bound ? '已绑定' : statusText[platform.state || 'not_configured'] || '未绑定'}
          </span>
        </div>
        <p className="mt-3 line-clamp-2 text-sm leading-6 text-(--ui-text-secondary)">
          {copy?.description || platform.description}
        </p>
      </div>
      <Tip label={bound ? '重新扫码绑定' : '扫码绑定'}>
        <Button aria-label={`${title}扫码绑定`} className="size-10 shrink-0 rounded-lg" onClick={onBind} variant="secondary">
          {bound ? <RefreshCw className="size-5" /> : <Plus className="size-5" />}
        </Button>
      </Tip>
    </article>
  )
}

function OnboardingDialog({
  onboarding,
  onClose,
  openExternal,
  open,
  platform,
  saving,
  starting
}: {
  onboarding: MessagingOnboardingSession | null
  onClose: () => void
  openExternal: (url: string) => Promise<boolean>
  open: boolean
  platform: MessagingPlatformInfo | null
  saving: boolean
  starting: boolean
}) {
  const title = platform ? displayTitle(platform) : 'IM频道'
  const copy = platform ? CHANNEL_COPY[platform.id as ImPlatformId] : null
  const busy = starting || saving || (onboarding && !['error', 'expired', 'cancelled'].includes(onboarding.status))

  return (
    <Dialog onOpenChange={value => (!value ? onClose() : undefined)} open={open}>
      <DialogContent className="max-w-md" onOpenAutoFocus={event => event.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{title}扫码绑定</DialogTitle>
          <DialogDescription>{copy?.scanHint || '请扫码完成授权。'}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-(--stroke-nous) bg-white p-4">
            {onboarding?.qr_data_url ? (
              <img alt={`${title}二维码`} className="h-64 w-64 object-contain" src={onboarding.qr_data_url} />
            ) : (
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
            )}
          </div>

          <div
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm',
              onboarding?.status === 'connected'
                ? 'bg-primary/10 text-primary'
                : onboarding?.status === 'error' || onboarding?.status === 'expired'
                  ? 'bg-destructive/10 text-destructive'
                  : 'bg-muted text-muted-foreground'
            )}
          >
            {onboarding?.status === 'connected' ? (
              <CheckCircle2 className="size-4" />
            ) : busy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            <span>{saving ? '正在保存配置...' : sessionMessage(onboarding)}</span>
          </div>

          {onboarding?.error && <InlineError>{onboarding.error}</InlineError>}

          {onboarding?.qr_payload && (
            <Button
              onClick={() => void openExternal(onboarding.qr_payload || '')}
              size="sm"
              type="button"
              variant="textStrong"
            >
              <ExternalLink className="size-4" />
              打开扫码链接
            </Button>
          )}
        </div>

        <DialogFooter>
          <Button onClick={onClose} type="button" variant="secondary">
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ChannelAvatar({ platform, title }: { platform: ImPlatformId; title: string }) {
  const icon = platform === 'dingtalk' ? 'organization' : platform === 'weixin' ? 'comment-discussion' : 'hubot'

  const tone =
    platform === 'dingtalk'
      ? 'bg-sky-500/10 text-sky-600'
      : platform === 'weixin'
        ? 'bg-emerald-500/10 text-emerald-600'
        : 'bg-rose-500/10 text-rose-600'

  return (
    <span
      aria-label={title}
      className={cn('flex size-11 shrink-0 items-center justify-center rounded-lg', tone)}
      role="img"
    >
      <Codicon name={icon} size="1.35rem" />
    </span>
  )
}

function InlineError({ children }: { children: string }) {
  return (
    <div className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {children}
    </div>
  )
}
