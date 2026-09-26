<template>
  <section class="page" data-module="project">
    <header class="page-head">
      <div>
        <h2>检测项目管理</h2>
        <p class="page-desc">维护检测项目，围绕项目编码、项目名称、检测方法、方法标准号做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测项目</button>
        <button class="btn" type="button" @click="exportRows">导出检测项目清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测项目记录</span>
      <span class="pager">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/project'
const columns = ["项目编码", "项目名称", "检测方法", "方法标准号", "检出限", "计量单位", "收费单价", "项目状态"]
const actions = ["启用项目", "提交修订", "停用项目"]
const stats = [{"label": "启用项目", "value": 0}, {"label": "待修订项目", "value": 0}, {"label": "本月新增项目", "value": 0}]
const filterFields = columns.slice(0, 3)
const PAGE_SIZE = 20

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})

// 只认最新一次查询的返回，避免上一轮的旧结果盖掉当前范围
let requestSeq = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasScope = computed(() => Object.keys(scopeQuery()).length > 0)
const emptyText = computed(() =>
  hasScope.value
    ? '当前范围条件下没有符合的检测项目，可调整项目编码等条件后重新查询'
    : '暂无检测项目数据，可先登记检测项目',
)

function scopeQuery() {
  const query: Record<string, string> = {}
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) query[field] = value
  }
  return query
}

function readScopeFromUrl() {
  const next: Record<string, string> = {}
  for (const field of filterFields) {
    const value = route.query[field]
    if (typeof value === 'string' && value.trim()) next[field] = value.trim()
  }
  filters.value = next
  const rawPage = Number(route.query.page)
  page.value = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
}

function syncScopeToUrl() {
  const query: Record<string, string> = { ...scopeQuery() }
  if (page.value > 1) query.page = String(page.value)
  void router.replace({ query })
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = {}
  page.value = 1
  void reload()
}

function goPage(next: number) {
  if (next < 1 || next > totalPages.value || next === page.value) return
  page.value = next
  void reload()
}

function exportRows() {
  const query = new URLSearchParams(scopeQuery()).toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测项目登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('检测项目动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测项目操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  syncScopeToUrl()
  const seq = ++requestSeq
  const params = new URLSearchParams({
    ...scopeQuery(),
    page: String(page.value),
    size: String(PAGE_SIZE),
  })
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('检测项目列表读取失败')
    }
    const payload = await response.json()
    if (seq !== requestSeq) return
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (!rows.value.length && total.value > 0 && page.value > totalPages.value) {
      // 范围收窄后页码越界时回到最后一页，而不是停在空页
      page.value = totalPages.value
      await reload()
    }
  } catch (error) {
    if (seq !== requestSeq) return
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '检测项目列表读取失败'
  }
}

onMounted(() => {
  readScopeFromUrl()
  void reload()
})
</script>
