<claude-mem-context>
# Memory Context

# [ahfl-working-Gpu] recent context, 2026-05-10 4:57pm GMT+5:30

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (15,705t read) | 575,667t work | 97% savings

### May 1, 2026
86 12:50a 🔵 Duplicate GPU Package Installs in batch-processor: Double-install Risk for paddlepaddle-gpu and torch
87 " 🔵 CUDA ABI: cu121 Index Correct for CUDA 12.2 Base Image Across Both Services
88 " 🔵 masking-engine Runs uvicorn with --workers 2 on Shared GPU: Potential OOM Risk
89 " 🔵 PaddleOCR Model Cache at /root/.paddlex vs Non-Root appuser: Runtime Download Risk
90 " 🔵 onnxruntime-gpu 1.17.0 in masking-engine Targets CUDA 11.8, Running on CUDA 12.2
91 " 🔵 Previously Fixed: GPU_ENABLED Split-Brain Bug Between engine.py and Core Modules
93 1:21a 🔴 Both Dockerfiles: appuser removed, masking-engine workers reduced to 1
94 1:23a ✅ Dockerfiles: added explanatory comments for root-user decision
96 1:25a ✅ 12pm GPU VM reminder updated to include root-user and worker-count Dockerfile changes
98 3:00a 🟣 DynamoDB Schema Validator Script Created
99 " 🔵 batch.py S3 Staging Upload Pattern — Code Confirmed
100 3:42a 🔵 batch.py DynamoDB Write Lifecycle Per File — 4-State Machine
101 3:45a 🔵 _get_skip_paths Uses Full Table Scan, Not GSI1 Query
102 " 🔵 S3 Pre-flight Bucket Validation Skipped During dry-run
103 " 🔵 Stale PROCESSING Record Cleanup on Startup
104 " 🔵 PDF Processing Chunked at 10 Pages with Blank Page Fallback
105 3:53a 🔵 Legacy bulk.py (v1.0) Architecture vs batch.py (v1.1) — Major Differences
S46 User asked to find main memory and session about email/mail thread — resulted in comprehensive audit of both AHFL project memory directory and observer sessions directory (May 1 at 4:02 AM)
113 5:56p 🟣 5 Code Quality Fixes Applied Locally — FIXES_APPLIED.md
114 " ✅ GPU_SYNC_PENDING.md Tracks 11 Files Awaiting GPU Server Sync
115 " ✅ GPU_SYNC_PATCHES.md: 2 Critical Patches With Copy-Paste Script for No-SSH Deployment
S48 User asked to find main memory and session about the mail — email_thread_ahfl.md located and read in full, revealing AHFL GPU setup communication history (May 1 at 8:27 PM)
S47 Second pass of memory audit — same exploration repeated, confirming email_thread_ahfl.md is the "mail" reference; Glob confirmed single email memory file exists (May 1 at 8:48 PM)
S49 AHFL GPU project full context synthesis — email thread + mem-search + graphify combined into complete project status (May 1 at 9:27 PM)
106 9:37p 🔵 AHFL GPU Migration — Full Project Status Reconstructed
107 9:38p 🔵 masking-engine vs batch-processor: Service vs One-Shot Job Runtime Difference
108 " 🔴 masking-engine --workers Reduced to 1; appuser Removed from Both Dockerfiles
109 " 🔴 batch-processor CUDA ABI Mismatch Fixed: cu118 → cu121
110 " 🔴 GPU_ENABLED Split-Brain Bug Fixed in engine.py and Core Modules
111 " 🔵 ahfl-working-Gpu Graphify Index: 3 Code Files, 25 Nodes, 22 Edges
112 " 🔵 ahfl-working-Gpu Codebase Structure: 3 Key God Nodes Identified
S50 User asked if prior work from two different sessions was known — memory reconstruction complete, but "two paths" reference is ambiguous and needs clarification (May 1 at 9:39 PM)
S52 onnxruntime-gpu CUDA mismatch investigation — full context rebuild from day1 file, mem-search (80 results), and deep observation retrieval (May 1 at 9:39 PM)
116 9:42p 🔵 GPU VM Day 1 Specs: Tesla T4, CUDA 13.0 Driver, Amazon Linux 2023 on EC2
117 " 🔴 Day 1 Build Failure: torch+cu121 Unresolvable from PyPI simple Index
118 " 🔵 Day 1 First Run: masking-engine HTTP 500 and gpu_available: false Despite CUDA Host
119 " 🔴 Day 1: dotenv ImportError in core/config.py and core/models/yolo_runner.py — Wrapped in try/except
120 " ✅ Day 1: requirements.txt Header Added with Full CUDA Version Matrix for PaddlePaddle
121 " 🔵 batch.py DynamoDB 4-State Machine Per File Confirmed
122 " 🔵 to_skip_file() Keyword Filter Not Migrated from bulk.py to batch.py
123 " 🔵 PADDLE_MODEL_DIR Config Unused — Not Wired Into PaddleOCR Constructor
124 " 🔵 batch.py preload_models() Has Duplicate GPU Warmup Block — Dead Code
S51 onnxruntime-gpu CUDA mismatch investigation — what version is masking-engine using and what should it use, with day1 terminal log as reference (May 1 at 9:42 PM)
S53 User asked whether claude-mem web UI at localhost:37701 shows all session chats and prompts (May 1 at 9:44 PM)
125 9:51p 🔵 User Queried claude-mem Web UI Accessibility at localhost:37701
126 9:52p 🔵 claude-mem Web API Search Endpoint Failed — Shell Glob Expansion
127 " 🔵 claude-mem Worker Confirmed Running — 6 Projects Indexed
128 " 🔵 claude-mem Search API Returns 0 Results for Empty Query on ahfl-working-Gpu
129 9:53p 🔵 claude-mem Context Inject API Confirmed — Full Timeline Retrieved for ahfl-working-Gpu
S54 User asked what data is accessible in claude-mem — full DB audit of observations, prompts, and schema (May 1 at 9:53 PM)
130 " 🔵 claude-mem SQLite DB — 114 Observations for ahfl-working-Gpu by Type
131 9:54p 🔵 claude-mem SQLite Schema — Full Table List Confirmed
132 " 🔵 claude-mem user_prompts Table Schema — Raw Prompt Text Stored Per Session
S55 User asked for complete data discovery workflow — primary session synthesized a reproducible 6-phase playbook (May 1 at 9:57 PM)
133 9:57p 🔵 to_skip_file() Keyword Filter Not Migrated from bulk.py to batch.py
134 " 🔵 claude-mem API: /api/context/inject Is Correct Enumeration Path, Not /api/search
135 " 🔵 email_thread_ahfl.md Not Found in ahfl-working-Gpu — File Absent from Current Directory
136 9:58p 🔵 Two Separate Claude Project Paths for AHFL GPU Work — Memory Fragmented Across Both
137 9:59p 🔵 email_thread_ahfl.md Lives in Old Project's Claude Memory Dir, Not in Repo
138 " 🔵 AHFL GPU Project Is Pure Python — No Go or TypeScript Files

Access 576k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>