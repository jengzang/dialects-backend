# Frontend Integration Guide

Guide for integrating the Guangdong Province Natural Village Analysis API with Vue 3 frontend applications.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Client Setup](#api-client-setup)
3. [Common Use Cases](#common-use-cases)
4. [State Management](#state-management)
5. [Error Handling](#error-handling)
6. [Performance Optimization](#performance-optimization)
7. [CORS Configuration](#cors-configuration)

---

## Quick Start

### Starting the API Server

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Search villages
curl "http://localhost:8000/api/village/search?query=水&limit=10"

# Get character frequency
curl "http://localhost:8000/api/character/frequency/global?top_n=20"
```

---

## API Client Setup

### Using Fetch API

Create a base API client (`src/api/client.js`):

```javascript
const API_BASE_URL = 'http://localhost:8000';

export async function apiGet(endpoint, params = {}) {
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  Object.keys(params).forEach(key => {
    if (params[key] !== null && params[key] !== undefined) {
      url.searchParams.append(key, params[key]);
    }
  });

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'API request failed');
  }

  return response.json();
}

export async function apiPost(endpoint, body = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'API request failed');
  }

  return response.json();
}
```

### Using Axios (Alternative)

```bash
npm install axios
```

```javascript
// src/api/client.js
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000, // 30 seconds for compute endpoints
});

// Response interceptor for error handling
client.interceptors.response.use(
  response => response.data,
  error => {
    const message = error.response?.data?.detail || error.message;
    return Promise.reject(new Error(message));
  }
);

export default client;
```

---

## Common Use Cases

### 1. Search Villages

**Scenario:** User types keyword in search box, display matching villages.

```javascript
// src/api/villages.js
import { apiGet } from './client';

export async function searchVillages(keyword, filters = {}) {
  return apiGet('/api/village/search', {
    query: keyword,
    city: filters.city || null,
    county: filters.county || null,
    limit: filters.limit || 20,
    offset: filters.offset || 0,
  });
}
```

**Vue Component:**

```vue
<template>
  <div>
    <input v-model="keyword" @input="onSearch" placeholder="搜索村名" />
    <div v-if="loading">加载中...</div>
    <div v-else-if="error">{{ error }}</div>
    <ul v-else>
      <li v-for="village in villages" :key="village.village_name">
        {{ village.village_name }} - {{ village.city }} {{ village.county }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { searchVillages } from '@/api/villages';
import { debounce } from 'lodash-es'; // npm install lodash-es

const keyword = ref('');
const villages = ref([]);
const loading = ref(false);
const error = ref(null);

const onSearch = debounce(async () => {
  if (keyword.value.length === 0) {
    villages.value = [];
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    villages.value = await searchVillages(keyword.value, { limit: 10 });
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}, 300); // Debounce 300ms
</script>
```

**Key Points:**
- Use debouncing to avoid excessive API calls while typing
- Handle loading and error states
- Clear results when keyword is empty

---

### 2. Display Character Frequency Chart

**Scenario:** Show top 20 high-frequency characters in a bar chart.

```javascript
// src/api/characters.js
import { apiGet } from './client';

export async function getGlobalCharFrequency(topN = 20) {
  return apiGet('/api/character/frequency/global', {
    top_n: topN,
    run_id: 'default',
  });
}
```

**Vue Component (with Chart.js):**

```bash
npm install chart.js vue-chartjs
```

```vue
<template>
  <div>
    <Bar :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { Bar } from 'vue-chartjs';
import { Chart, registerables } from 'chart.js';
import { getGlobalCharFrequency } from '@/api/characters';

Chart.register(...registerables);

const frequencyData = ref([]);

const chartData = computed(() => ({
  labels: frequencyData.value.map(item => item.character),
  datasets: [{
    label: '字符频次',
    data: frequencyData.value.map(item => item.frequency),
    backgroundColor: 'rgba(54, 162, 235, 0.5)',
  }],
}));

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { display: false },
    title: { display: true, text: '高频字符 Top 20' },
  },
};

onMounted(async () => {
  try {
    frequencyData.value = await getGlobalCharFrequency(20);
  } catch (err) {
    console.error('Failed to load frequency data:', err);
  }
});
</script>
```

---

### 3. Regional Tendency Heatmap

**Scenario:** Display character tendency across regions as a heatmap.

```javascript
// src/api/characters.js
export async function getCharTendencyByChar(character, regionLevel = 'city') {
  return apiGet('/api/character/tendency/by-char', {
    character,
    region_level: regionLevel,
    run_id: 'default',
  });
}
```

**Implementation Strategy:**
1. Fetch tendency data for selected character
2. Map region names to geographic coordinates (if available)
3. Use a map library (e.g., Leaflet, Mapbox) to render heatmap
4. Color intensity based on z-score values

**Data Processing:**

```javascript
function processTendencyForHeatmap(tendencyData) {
  return tendencyData.map(item => ({
    region: item.region_name,
    value: item.z_score,
    color: getColorByZScore(item.z_score),
  }));
}

function getColorByZScore(zScore) {
  if (zScore > 2) return '#d73027'; // High tendency (red)
  if (zScore > 0) return '#fee08b'; // Medium tendency (yellow)
  if (zScore > -2) return '#d9ef8b'; // Low tendency (light green)
  return '#1a9850'; // Very low tendency (green)
}
```

---

### 4. Run Clustering Analysis

**Scenario:** User selects clustering parameters, run analysis, display results.

```javascript
// src/api/compute.js
import { apiPost } from './client';

export async function runClustering(params) {
  return apiPost('/api/compute/clustering/run', {
    region_level: params.regionLevel || 'county',
    algorithm: params.algorithm || 'kmeans',
    k: params.k || 4,
    features: {
      use_semantic: params.useSemanticFeatures ?? true,
      use_morphology: params.useMorphologyFeatures ?? true,
      use_diversity: params.useDiversityFeatures ?? true,
    },
    preprocessing: {
      standardize: params.standardize ?? true,
      use_pca: params.usePCA ?? false,
      pca_n_components: params.pcaComponents || 10,
    },
    region_filter: params.regionFilter || null,
    random_state: 42,
  });
}
```

**Vue Component:**

```vue
<template>
  <div>
    <div class="controls">
      <select v-model="algorithm">
        <option value="kmeans">K-Means</option>
        <option value="dbscan">DBSCAN</option>
        <option value="gmm">GMM</option>
      </select>

      <input v-if="algorithm !== 'dbscan'" v-model.number="k" type="number" min="2" max="10" />

      <button @click="runAnalysis" :disabled="loading">
        {{ loading ? '分析中...' : '运行聚类' }}
      </button>
    </div>

    <div v-if="loading" class="progress">
      <div class="spinner"></div>
      <p>正在计算，请稍候...</p>
    </div>

    <div v-else-if="result">
      <h3>聚类结果</h3>
      <p>执行时间: {{ result.execution_time_ms }}ms</p>
      <p>轮廓系数: {{ result.metrics.silhouette_score.toFixed(3) }}</p>

      <div v-for="cluster in result.cluster_profiles" :key="cluster.cluster_id">
        <h4>聚类 {{ cluster.cluster_id }} ({{ cluster.region_count }} 个区域)</h4>
        <p>{{ cluster.regions.join(', ') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { runClustering } from '@/api/compute';

const algorithm = ref('kmeans');
const k = ref(4);
const loading = ref(false);
const result = ref(null);

async function runAnalysis() {
  loading.value = true;
  result.value = null;

  try {
    result.value = await runClustering({
      algorithm: algorithm.value,
      k: k.value,
      regionLevel: 'county',
    });
  } catch (err) {
    alert('聚类分析失败: ' + err.message);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
```

**Key Points:**
- Show loading indicator during computation (can take 1-10 seconds)
- Disable submit button while loading
- Handle timeout errors (408) gracefully
- Cache results automatically (5-minute TTL)

---

### 5. Pagination

**Scenario:** Display paginated village search results.

```vue
<template>
  <div>
    <ul>
      <li v-for="village in villages" :key="village.village_name">
        {{ village.village_name }}
      </li>
    </ul>

    <div class="pagination">
      <button @click="prevPage" :disabled="page === 1">上一页</button>
      <span>第 {{ page }} 页</span>
      <button @click="nextPage" :disabled="villages.length < pageSize">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { searchVillages } from '@/api/villages';

const keyword = ref('水');
const page = ref(1);
const pageSize = ref(20);
const villages = ref([]);

async function loadVillages() {
  const offset = (page.value - 1) * pageSize.value;
  villages.value = await searchVillages(keyword.value, {
    limit: pageSize.value,
    offset,
  });
}

function prevPage() {
  if (page.value > 1) {
    page.value--;
  }
}

function nextPage() {
  page.value++;
}

watch([page, keyword], loadVillages, { immediate: true });
</script>
```

---

## State Management

### Using Pinia (Recommended)

```bash
npm install pinia
```

**Store Definition (`src/stores/villages.js`):**

```javascript
import { defineStore } from 'pinia';
import { searchVillages, getVillageDetail } from '@/api/villages';

export const useVillagesStore = defineStore('villages', {
  state: () => ({
    searchResults: [],
    selectedVillage: null,
    loading: false,
    error: null,
  }),

  actions: {
    async search(keyword, filters = {}) {
      this.loading = true;
      this.error = null;

      try {
        this.searchResults = await searchVillages(keyword, filters);
      } catch (err) {
        this.error = err.message;
        this.searchResults = [];
      } finally {
        this.loading = false;
      }
    },

    async loadDetail(villageName, city, county) {
      this.loading = true;
      this.error = null;

      try {
        this.selectedVillage = await getVillageDetail(villageName, city, county);
      } catch (err) {
        this.error = err.message;
        this.selectedVillage = null;
      } finally {
        this.loading = false;
      }
    },
  },
});
```

**Usage in Component:**

```vue
<script setup>
import { useVillagesStore } from '@/stores/villages';

const store = useVillagesStore();

function handleSearch(keyword) {
  store.search(keyword);
}
</script>

<template>
  <div>
    <div v-if="store.loading">加载中...</div>
    <div v-else-if="store.error">{{ store.error }}</div>
    <ul v-else>
      <li v-for="village in store.searchResults" :key="village.village_name">
        {{ village.village_name }}
      </li>
    </ul>
  </div>
</template>
```

---

## Error Handling

### Centralized Error Handler

```javascript
// src/utils/errorHandler.js
export function handleApiError(error) {
  if (error.message.includes('timeout')) {
    return '请求超时，请稍后重试';
  }

  if (error.message.includes('404')) {
    return '未找到相关数据';
  }

  if (error.message.includes('Network')) {
    return '网络连接失败，请检查网络';
  }

  return error.message || '未知错误';
}
```

**Usage:**

```javascript
import { handleApiError } from '@/utils/errorHandler';

try {
  const data = await searchVillages(keyword);
} catch (err) {
  const userMessage = handleApiError(err);
  alert(userMessage);
}
```

### Timeout Handling

For long-running compute endpoints:

```javascript
async function runClusteringWithTimeout(params, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch('http://localhost:8000/api/compute/clustering/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    return response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('请求超时，请减少数据量或简化参数');
    }
    throw err;
  }
}
```

---

## Performance Optimization

### 1. Debouncing Search Input

```javascript
import { debounce } from 'lodash-es';

const debouncedSearch = debounce(async (keyword) => {
  const results = await searchVillages(keyword);
  // Update UI
}, 300);
```

### 2. Caching API Responses

```javascript
// Simple in-memory cache
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function cachedApiGet(endpoint, params) {
  const cacheKey = `${endpoint}:${JSON.stringify(params)}`;
  const cached = cache.get(cacheKey);

  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await apiGet(endpoint, params);
  cache.set(cacheKey, { data, timestamp: Date.now() });

  return data;
}
```

### 3. Lazy Loading Components

```javascript
// Router configuration
const routes = [
  {
    path: '/clustering',
    component: () => import('@/views/ClusteringView.vue'), // Lazy load
  },
];
```

### 4. Pagination Strategy

- Use `limit` and `offset` for large result sets
- Default `limit=20` is reasonable
- Avoid loading all results at once

### 5. Progress Indicators

For compute endpoints (>1 second):
- Show spinner or progress bar
- Display estimated time if known
- Allow cancellation if possible

---

## CORS Configuration

### Development (Current)

API allows all origins:

```python
# api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # All origins allowed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Frontend can call API directly from `localhost:5173` (Vite default).

### Production

Restrict to your domain:

```python
# api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
```

### Handling Preflight Requests

CORS preflight (OPTIONS) requests are handled automatically by FastAPI middleware. No additional configuration needed.

---

## Best Practices Summary

1. **Debounce search inputs** - Avoid excessive API calls
2. **Show loading states** - Improve perceived performance
3. **Handle errors gracefully** - Display user-friendly messages
4. **Use pagination** - Don't load all data at once
5. **Cache responses** - Reduce redundant requests (API caches compute results for 5 minutes)
6. **Timeout handling** - Compute endpoints can take 1-30 seconds
7. **Validate inputs** - Check parameters before API calls
8. **Use environment variables** - Store API base URL in `.env`

---

## Environment Configuration

**`.env` file:**

```
VITE_API_BASE_URL=http://localhost:8000
```

**Usage:**

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
```

---

## See Also

- [API Reference](API_REFERENCE.md) - Complete endpoint documentation
- [API Deployment Guide](API_DEPLOYMENT_GUIDE.md) - Deployment instructions
- [API Quick Reference](API_QUICK_REFERENCE.md) - Cheat sheet
- [Swagger UI](http://localhost:8000/docs) - Interactive API testing