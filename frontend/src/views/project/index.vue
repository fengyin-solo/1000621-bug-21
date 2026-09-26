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
      <div class="pager">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
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
const statuses = ["草稿", "已启用", "待修订", "已停用"]
const stats = [{"label": "启用项目", "value": 0}, {"label": "待修订项目", "value": 0}, {"label": "本月新增项目", "value": 0}]
const PAGE_SIZE = 20
// 筛选框与后端查询参数的对应关系：列表、分页与导出共用这一套口径
const FILTER_PARAMS: Record<string, string> = { "项目编码": "keyword", "项目名称": "name", "检测方法": "method" }

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = Object.keys(FILTER_PARAMS)
// 只采纳最新一次响应，避免慢请求后到、把上一轮条件的结果盖回界面
let requestSeq = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasFilter = computed(() => filterFields.some((field) => (filters.value[field] ?? '').trim()))
const emptyText = computed(() =>
  hasFilter.value
    ? '没有符合当前条件的检测项目，可调整或清空检索条件后重试'
    : '暂无检测项目数据，可先登记检测项目',
)

function activeFilters(): Record<string, string> {
  const active: Record<string, string> = {}
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      active[field] = value
    }
  }
  return active
}

function buildQuery(): URLSearchParams {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries(activeFilters())) {
    params.set(FILTER_PARAMS[field], value)
  }
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  return params
}

// 把当前条件写回地址栏：刷新或重新进入后范围条件不丢
function syncUrl() {
  const query: Record<string, string> = {}
  for (const [field, value] of Object.entries(activeFilters())) {
    query[FILTER_PARAMS[field]] = value
  }
  if (page.value > 1) {
    query.page = String(page.value)
  }
  void router.replace({ query })
}

function restoreFromUrl() {
  const restored: Record<string, string> = {}
  for (const field of filterFields) {
    const value = route.query[FILTER_PARAMS[field]]
    if (typeof value === 'string' && value.trim()) {
      restored[field] = value.trim()
    }
  }
  filters.value = restored
  const rawPage = Number(route.query.page)
  page.value = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
}

function applyFilters() {
  page.value = 1
  syncUrl()
  void reload()
}

function resetFilters() {
  filters.value = {}
  page.value = 1
  syncUrl()
  void reload()
}

function goPage(target: number) {
  if (target < 1 || target > totalPages.value || target === page.value) {
    return
  }
  page.value = target
  syncUrl()
  void reload()
}

function exportRows() {
  const params = buildQuery()
  params.delete('page')
  params.delete('size')
  window.open(`${ENDPOINT}/export?${params.toString()}`, '_blank')
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
  const seq = ++requestSeq
  try {
    const response = await request(`${ENDPOINT}?${buildQuery().toString()}`)
    if (!response.ok) {
      throw new Error('检测项目列表读取失败')
    }
    const payload = await response.json()
    if (seq !== requestSeq) {
      return
    }
    const items = payload.items ?? []
    const count = payload.total ?? items.length
    if (!items.length && count > 0 && page.value > 1) {
      // 当前页已被清空（例如刚停用了本页最后一条），退回还有数据的最后一页
      page.value = Math.ceil(count / PAGE_SIZE)
      syncUrl()
      await reload()
      return
    }
    rows.value = items
    total.value = count
  } catch (error) {
    if (seq !== requestSeq) {
      return
    }
    errorMessage.value = error instanceof Error ? error.message : '检测项目列表读取失败'
  }
}

onMounted(() => {
  restoreFromUrl()
  void reload()
})
</script>
