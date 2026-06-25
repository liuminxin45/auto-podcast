import process from "node:process"
import type { NewsItem } from "@shared/types"
import { rss2json } from "#/utils/rss2json"
import { defineSource } from "#/utils/source"

interface CustomFeed {
  title?: string
  url: string
}

function normalizeFeed(value: unknown): CustomFeed | undefined {
  if (typeof value === "string") {
    const url = value.trim()
    return url ? { url } : undefined
  }
  if (!value || typeof value !== "object") return undefined
  const candidate = value as Partial<CustomFeed>
  const url = String(candidate.url || "").trim()
  if (!url) return undefined
  const title = candidate.title ? String(candidate.title).trim() : undefined
  return { title, url }
}

function parseFeeds(): CustomFeed[] {
  const raw = String(process.env.AUTO_PODCAST_NEWSNOW_FEEDS || "").trim()
  if (!raw) return []

  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return parsed.map(normalizeFeed).filter(Boolean) as CustomFeed[]
    }
  } catch {
    // Fall back to newline/comma separated values.
  }

  return raw
    .split(/\r?\n|,/)
    .map(normalizeFeed)
    .filter(Boolean) as CustomFeed[]
}

export default defineSource(async () => {
  const feeds = parseFeeds()
  if (!feeds.length) {
    throw new Error("AUTO_PODCAST_NEWSNOW_FEEDS is empty")
  }

  const settled = await Promise.allSettled(
    feeds.map(async (feed) => {
      const data = await rss2json(feed.url)
      if (!data?.items?.length) return []
      const sourceTitle = feed.title || data.title || feed.url
      return data.items.map<NewsItem>((item) => ({
        id: `${feed.url}#${item.link}`,
        title: item.title,
        url: item.link,
        pubDate: item.created,
        extra: {
          info: sourceTitle,
        },
      }))
    }),
  )

  const items = settled.flatMap(result => result.status === "fulfilled" ? result.value : [])
  if (!items.length) {
    const errors = settled
      .filter(result => result.status === "rejected")
      .map(result => result.reason instanceof Error ? result.reason.message : String(result.reason))
    throw new Error(errors.length ? errors.join("; ") : "No custom feed items")
  }

  return items.slice(0, 30)
})
