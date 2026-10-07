import type { EventKind } from './types'
import { phraseKey } from './format'

/** Site-speaker voice alerts: pre-generated clips (/voices/<key>_<lang>.mp3) played in sequence. */
class VoicePlayer {
  enabled = false
  languages: string[] = ['ar', 'en', 'ur', 'hi', 'bn']
  private queue: string[] = []
  private current: HTMLAudioElement | null = null
  private lastPlayed = new Map<string, number>()
  private listeners = new Set<() => void>()

  setEnabled(on: boolean) {
    this.enabled = on
    if (!on) this.stop()
    this.listeners.forEach((fn) => fn())
  }

  subscribe(fn: () => void) {
    this.listeners.add(fn)
    return () => void this.listeners.delete(fn)
  }

  /** Queue the alert for an event; repeats of the same alert within 15 s are skipped. */
  announce(kind: EventKind, item: string | null, critical = false) {
    const key = phraseKey(kind, item)
    if (!this.enabled || !key) return
    const now = Date.now()
    if ((this.lastPlayed.get(key) ?? 0) > now - 15_000) return
    this.lastPlayed.set(key, now)
    const clips = this.languages.map((l) => `/voices/${key}_${l}.mp3`)
    if (critical) {
      this.stop()
      this.queue = clips
    } else if (this.queue.length < 10) {
      this.queue.push(...clips)
    }
    this.next()
  }

  preview(key: string, lang: string) {
    this.stop()
    this.queue = [`/voices/${key}_${lang}.mp3`]
    this.next()
  }

  stop() {
    this.queue = []
    if (this.current) {
      this.current.pause()
      this.current = null
    }
  }

  private next() {
    if (this.current) return
    const src = this.queue.shift()
    if (!src) return
    const audio = new Audio(src)
    this.current = audio
    const done = () => {
      if (this.current === audio) this.current = null
      this.next()
    }
    audio.onended = done
    audio.onerror = done
    audio.play().catch(done)
  }
}

export const voice = new VoicePlayer()
