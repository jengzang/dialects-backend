#!/usr/bin/env python3
"""Generate complete villagesML API documentation"""

doc_content = """# villagesML API Complete Reference

**Version:** 1.0
**Base URL:** `http://127.0.0.1:5000/api/villages`
**Last Updated:** 2026-02-23

## Overview

This document provides a complete reference for all villagesML (广东省自然村分析系统) API endpoints. The system provides linguistic analysis and visualization capabilities for 285,860+ Guangdong natural villages.

**Important Notes:**
- All endpoints are prefixed with `/api/villages`
- Most endpoints support optional `run_id` parameter (defaults to active version)
- Compute endpoints require authentication
- Admin write operations require admin role
- **Note:** `/api/villages/regions` does NOT exist. Use `/api/villages/regional/aggregates/{city|county|town}` instead

---

## Table of Contents

1. [Character Analysis](#1-character-analysis) (10 endpoints)
2. [Village Data](#2-village-data) (7 endpoints)
3. [Metadata](#3-metadata) (3 endpoints)
4. [Semantic Analysis](#4-semantic-analysis) (14 endpoints)
5. [Clustering Analysis](#5-clustering-analysis) (9 endpoints)
6. [Spatial Analysis](#6-spatial-analysis) (8 endpoints)
7. [N-gram Analysis](#7-n-gram-analysis) (5 endpoints)
8. [Pattern Analysis](#8-pattern-analysis) (4 endpoints)
9. [Regional Aggregates](#9-regional-aggregates) (5 endpoints)
10. [Compute APIs](#10-compute-apis) (10 endpoints)
11. [Admin APIs](#11-admin-apis) (6 endpoints)

**Total: 74 endpoints**

---

## 1. Character Analysis

### 1.1 Character Frequency

**Base Path:** `/api/villages/character/frequency`

#### GET `/global`
Get global character frequency statistics across all village names.

**Query Parameters:**
