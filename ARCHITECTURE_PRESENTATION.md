# DoorDesignPython - Architecture Presentation

## Complete PowerPoint Slide Content & Structure

---

## **Slide 1: Title Slide**

### Door Design DXF Generator

**Automated CAD File Generation System**

- **Technology Stack:** Python, FastAPI, ezdxf
- **Purpose:** Generate DXF/PDF files from door specifications
- **Modes:** Single door generation & Batch processing from Excel

---

## **Slide 2: System Overview**

### High-Level Architecture

```
┌─────────────────┐
│   Web Browser   │ ← User Interface
│   (Frontend)    │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│   FastAPI       │ ← API Layer
│   Backend       │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬────────────┐
    ▼         ▼          ▼            ▼
┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│ Geometry│ │  DXF   │ │ Packing  │ │ Auth     │
│ Engine  │ │ Engine │ │ Engine   │ │ Service  │
└─────────┘ └────────┘ └──────────┘ └──────────┘
    │           │          │
    └───────────┴──────────┘
                │
                ▼
        ┌───────────────┐
        │ Output Files  │
        │ (.dxf/.pdf)   │
        └───────────────┘
```

**Key Components:**

- Static HTML/JS Frontend
- FastAPI REST Backend
- Geometry Calculation Engine
- DXF/PDF Generation
- Bin Packing Algorithm
- Authentication System

---

## **Slide 3: Frontend Architecture**

### User Interface Layer

**File:** `frontend/app.js`, `frontend/index.html`

**Features:**

1. **Dual Mode Interface**

   - Single Mode: Manual parameter entry
   - Bulk Mode: Excel file upload

2. **Input Validation**

   - Width/Height: 200-3000mm
   - Allowances: 0-50mm
   - Real-time feedback

3. **Door Configuration**

   - Type: Single/Double
   - Subtype: Normal/Fire
   - Fire options (3 for single, 2 for double)
   - Hole offset configuration
   - Custom allowances

4. **Actions**
   - Generate DXF
   - Generate PDF
   - Preview Geometry (JSON)

**Communication:**

- REST API calls via `fetch()`
- JSON payload construction
- File download handling

---

## **Slide 4: API Layer - FastAPI Backend**

### Request Flow & Endpoints

**File:** `fastapi_app/main.py`

### **Main Endpoints:**

| Endpoint                | Method | Purpose                      |
| ----------------------- | ------ | ---------------------------- |
| `/`                     | GET    | Serve frontend (index.html)  |
| `/generate-dxf/`        | POST   | Excel → ZIP (batch mode)     |
| `/generate-single-dxf/` | POST   | JSON → DXF/PDF (single mode) |
| `/dxf/geometry`         | POST   | JSON → Geometry preview      |
| `/health`               | GET    | Health check                 |
| `/register`             | POST   | User registration            |
| `/check-auth`           | GET    | Auth status                  |

### **Middleware Stack:**

1. **IP Whitelist** (optional via `ALLOWED_IPS` env)
2. **Authentication** (cookie-based, optional via `REQUIRE_AUTH` env)
3. **Request Logging** (per-request JSON files + app.log)
4. **CORS** (allows cross-origin requests)

### **Request Processing:**

```
HTTP Request
    ↓
IP Whitelist Check
    ↓
Authentication Check
    ↓
Request Logging (start)
    ↓
Route Handler
    ↓
Response Generation
    ↓
Request Logging (finish)
    ↓
HTTP Response
```

---

## **Slide 5: Data Models (Pydantic Schemas)**

### Input & Output Contracts

**File:** `fastapi_app/schemas_input.py`

### **Input Schema: DoorDXFRequest**

```python
DoorDXFRequest
├── mode: str ("single" | "generate")
├── door: DoorInfo
│   ├── category: "Single" | "Double"
│   ├── type: "Normal" | "Fire"
│   ├── option: Fire door variant
│   ├── hole_offset: "150x40" etc.
│   └── default_allowance: "yes" | "no"
├── dimensions: DimensionInfo
│   ├── width_measurement
│   ├── height_measurement
│   ├── left_side_allowance_width
│   ├── right_side_allowance_width
│   ├── top_side_allowance_height
│   └── bottom_side_allowance_height
├── metadata: Metadata
│   ├── label
│   ├── file_name
│   ├── width/height (for packing)
│   ├── rotated
│   └── offset
└── defaults: DefaultInfo
    ├── door_minus_measurement_width: 68
    ├── door_minus_measurement_height: 70
    ├── bending_width: 31
    └── bending_height: 24
```

**File:** `fastapi_app/schemas_output.py`

### **Output Schema: SchemasOutput**

```python
SchemasOutput
├── door_category: "Single" | "Double"
├── door_type: "Normal" | "Fire"
├── option: Optional fire variant
├── metadata: Metadata (enriched)
└── geometry: Geometry
    ├── frames: List[Frame]
    ├── cutouts: List[Cutout]
    ├── holes: List[Hole]
    ├── annotations: Dict[str, List[Annotation]]
    └── labels: List[Label]
```

---

## **Slide 6: Geometry Generation Pipeline**

### Core Calculation Engine

**File:** `geometry/door_geometry.py`

### **Pipeline Stages:**

```
DoorDXFRequest
    ↓
┌─────────────────────────┐
│ 1. prepare_dimensions() │ ← Normalize inputs, compute derived values
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 2. create_base_frames() │ ← Generate outer/inner frames (single/double)
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 3. create_handles()     │ ← Add handle cutout geometry
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 4. generate_cutouts()   │ ← Fire door glass panels, custom cutouts
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 5. generate_holes()     │ ← Circular holes (handles, locks)
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 6. apply_transform()    │ ← Rotate & translate if needed (packing)
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 7. normalize_geometry() │ ← Shift to origin (min x,y = 0)
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 8. generate_annotations()│ ← Dimension lines, labels
└──────────┬──────────────┘
           ↓
┌─────────────────────────┐
│ 9. create_labels()      │ ← Door name, dimensions text
└──────────┬──────────────┘
           ↓
    SchemasOutput
```

**Key Features:**

- Modular pipeline (each stage is separate module)
- Coordinate system normalization
- Support for rotation (for packing optimization)
- Annotation generation (dimensions, notes, leaders)

---

## **Slide 7: Geometry Modules Details**

### Specialized Calculation Units

| Module                 | File                      | Purpose                                            |
| ---------------------- | ------------------------- | -------------------------------------------------- |
| **Prepare Dimensions** | `prepare_dimensions.py`   | Input normalization, derived calculations          |
| **Base Frames**        | `create_base_frames.py`   | Outer/inner frame polygons for single/double doors |
| **Handles**            | `create_handles.py`       | Handle cutout rectangles                           |
| **Cutouts**            | `generate_cutouts.py`     | Fire door glass panels, custom shapes              |
| **Holes**              | `generate_holes.py`       | Circular holes (locks, handles)                    |
| **Transform**          | `apply_transform.py`      | Rotation + translation for packing                 |
| **Annotations**        | `generate_annotations.py` | Dimension lines, notes, leaders                    |
| **Labels**             | `add_labels.py`           | Text labels (door name, size)                      |
| **Utilities**          | `utilis.py`               | Bounding box, dimensions, helpers                  |

### **Example: Fire Door Cutouts**

- Standard: Fixed glass panels at specific positions
- Top-Fixed: Flexible bottom, fixed top glass
- Bottom-Fixed: Flexible top, fixed bottom glass
- Four Glass (Double): 4 aligned glass panels

---

## **Slide 8: DXF Generation & Export**

### CAD File Creation

**File:** `DoorDrawingGenerator.py`

### **DXF Generation Flow:**

```
SchemasOutput (geometry)
    ↓
┌────────────────────────┐
│ Create ezdxf Document  │ ← DXF R2010 format
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Create Layers          │ ← CUT, DIMENSIONS, BIN
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Draw Frames            │ ← Polylines (outer/inner)
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Draw Cutouts           │ ← Polylines (glass panels)
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Draw Holes             │ ← Circles (handle/lock holes)
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Draw Annotations       │ ← Dimension lines, text
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Draw Labels            │ ← Door name, dimensions
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Save DXF File          │ ← Write to disk
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Optional: Export PDF   │ ← Headless conversion (matplotlib)
└────────────────────────┘
```

**Key Features:**

- Layer management (CUT, DIMENSIONS, BIN)
- DXF styles & dimstyles
- Coordinate transformation support
- Annotation scaling
- PDF export capability

---

## **Slide 9: Batch Processing & Bin Packing**

### Excel to ZIP Workflow

**Files:** `BatchDoorDXFGenerator.py`, `DoorRectPack.py`, `bin_dxf_generator.py`

### **Batch Processing Flow:**

```
Excel File (.xlsx/.xlsm)
    ↓
┌────────────────────────┐
│ pandas.read_excel()    │ ← Parse rows
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ get_door_rectangles()  │ ← Extract dimensions, parameters
└──────────┬─────────────┘
           ↓
    List of rectangles
    (width, height, name)
           ↓
┌────────────────────────┐
│ pack_rectangles()      │ ← rectpack library (bin packing)
└──────────┬─────────────┘
           ↓
    Bins (sheets)
    with placements
           ↓
┌────────────────────────┐
│ For each bin:          │
│   Create DXF doc       │
│   Draw bin outline     │
│   For each placement:  │
│     Generate geometry  │
│     Apply rotation     │
│     Apply translation  │
│     Draw to DXF        │
└──────────┬─────────────┘
           ↓
┌────────────────────────┐
│ Create ZIP archive     │ ← All DXF files
└──────────┬─────────────┘
           ↓
    ZIP File Download
```

### **Bin Packing Algorithm:**

- Library: `rectpack` (2D rectangle packing)
- Sheet size: Default 1250x2500mm (configurable)
- Rotation: Attempts both orientations for optimization
- Multiple sheets: Automatically creates bins as needed

### **Output:**

- One DXF file per sheet (bin)
- ZIP archive containing all sheets
- Timestamp-based naming

---

## **Slide 10: Authentication System**

### Optional Security Layer

**Files:** `fastapi_app/routes/auth.py`, `fastapi_app/services/user_service.py`

### **Authentication Flow:**

```
User → /register
    ↓
Generate UUID token
    ↓
Store in users.txt
(token | status | username | timestamp)
    ↓
Create hashed cookie
    ↓
Set HTTP-only cookie
    ↓
User requests protected resource
    ↓
Auth middleware checks cookie
    ↓
Validate against users.txt
    ↓
Allow/Deny access
```

### **Features:**

- **Token-based:** UUID tokens stored in file
- **Cookie-based:** HTTP-only secure cookies
- **Status management:** Active/inactive users
- **Admin tools:** `tools/auth_admin.py` for user management
- **Optional:** Controlled by `REQUIRE_AUTH` env variable

### **Public Paths (no auth required):**

- `/static`, `/register`, `/check-auth`, `/health`, `/docs`

---

## **Slide 11: Configuration & Environment**

### Runtime Settings

### **Environment Variables:**

| Variable              | Purpose                          | Default          |
| --------------------- | -------------------------------- | ---------------- |
| `PORT`                | Server port                      | 8000             |
| `ALLOWED_IPS`         | IP whitelist (CIDR)              | "" (all allowed) |
| `REQUIRE_AUTH`        | Enable authentication            | false            |
| `FULL_BODY_LOGGING`   | Log full request/response bodies | true             |
| `MAX_FULL_BODY_BYTES` | Max body size to log             | 5MB              |
| `DEBUG_WAIT`          | Wait for debugger (debugpy)      | 0                |

### **Configuration Files:**

- `requirements.txt` - Python dependencies
- `annotation_styles.json` - DXF annotation styling
- `.env` - Environment variables (gitignored)
- `users.txt` - Registered users (if auth enabled)

### **Logging:**

- **Main log:** `fastapi_app/logs/app.log` (rotating, 10MB max)
- **Per-request logs:** `fastapi_app/logs/requests/{request_id}.json`
- **Error logs:** `fastapi_app/logs/errors/{request_id}.json`

---

## **Slide 12: Deployment Architecture**

### Production Considerations

### **Deployment Options:**

1. **Local Development**

   ```powershell
   python -m uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Production (uvicorn)**

   ```bash
   uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Containerized (Docker)**
   - Not currently implemented
   - Recommended for production

### **Architecture Diagram:**

```
Internet
    ↓
[Reverse Proxy] (nginx/caddy)
    ↓ HTTPS
[Load Balancer] (optional)
    ↓
[uvicorn workers] × N
    ↓
[DoorDesignPython]
    ↓
[File System] (output/, logs/)
```

### **Production Checklist:**

- ✅ Set `ALLOWED_IPS` for IP whitelisting
- ✅ Enable `REQUIRE_AUTH` if needed
- ✅ Configure reverse proxy (nginx)
- ✅ Set up SSL/TLS certificates
- ✅ Configure log rotation
- ✅ Monitor disk space (output/, logs/)
- ✅ Set resource limits (CPU, memory)

---

## **Slide 13: Data Flow - Single Mode**

### Request to Response Journey

```
┌──────────────┐
│ User fills   │
│ form in      │ 1. User Input
│ frontend     │
└──────┬───────┘
       │ POST /generate-single-dxf/
       ↓
┌──────────────┐
│ FastAPI      │ 2. Validation
│ validates    │    (Pydantic)
│ DoorDXFRequest│
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ prepare_     │ 3. Normalize inputs
│ dimensions() │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Geometry     │ 4. Generate geometry
│ Pipeline     │    (frames, cutouts, holes)
│ (8 stages)   │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ DoorDrawing  │ 5. Create DXF
│ Generator    │    (ezdxf)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Optional:    │ 6. Export PDF
│ PDF export   │    (matplotlib)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ FileResponse │ 7. Send file to browser
│ (DXF/PDF)    │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Browser      │ 8. Download file
│ downloads    │
└──────────────┘
```

**Typical Response Time:** < 2 seconds for single door

---

## **Slide 14: Data Flow - Bulk Mode**

### Excel to ZIP Journey

```
┌──────────────┐
│ User uploads │ 1. Excel file
│ Excel file   │    (multi-row)
└──────┬───────┘
       │ POST /generate-dxf/
       ↓
┌──────────────┐
│ FastAPI      │ 2. Save temp file
│ receives     │
│ multipart    │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ pandas reads │ 3. Parse rows
│ Excel        │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ get_door_    │ 4. Extract rectangles
│ rectangles() │    + parameters
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ pack_        │ 5. Bin packing
│ rectangles() │    (rectpack)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ For each     │ 6. Generate DXF per bin
│ bin:         │    (with rotations/offsets)
│   - Bin 1.dxf│
│   - Bin 2.dxf│
│   - ...      │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Create ZIP   │ 7. Archive all DXFs
│ archive      │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ FileResponse │ 8. Send ZIP to browser
│ (ZIP)        │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│ Browser      │ 9. Download ZIP
│ downloads    │
└──────────────┘
```

**Typical Response Time:** 5-30 seconds (depends on row count)

---

## **Slide 15: Technology Stack & Dependencies**

### Core Technologies

### **Backend:**

- **Python 3.9+** - Primary language
- **FastAPI** - Modern async web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation & schemas

### **CAD/Graphics:**

- **ezdxf** - DXF file creation/manipulation
- **matplotlib** - PDF export (headless)
- **rectpack** - 2D bin packing algorithm

### **Data Processing:**

- **pandas** - Excel file parsing
- **openpyxl** - Excel file engine

### **Utilities:**

- **python-dotenv** - Environment variable management
- **logging** - Application logging

### **Frontend:**

- **Vanilla JavaScript** - No frameworks
- **HTML5/CSS3** - Modern web standards
- **Fetch API** - HTTP requests

### **Authentication:**

- **UUID** - Token generation
- **hashlib** - Cookie hashing
- **File-based storage** - users.txt

---

## **Slide 16: Error Handling & Logging**

### Observability & Debugging

### **Error Handling Layers:**

1. **Pydantic Validation**

   - Automatic input validation
   - Type checking
   - Range validation

2. **Try-Catch Blocks**

   - Geometry calculation errors
   - DXF generation errors
   - File I/O errors

3. **Global Exception Handler**
   - Catches unhandled exceptions
   - Logs full traceback
   - Returns JSON error with request_id

### **Logging Strategy:**

```
Request arrives
    ↓
┌─────────────────────────┐
│ Request Middleware      │
│ - Log request.start     │
│ - Capture body preview  │
│ - Generate request_id   │
└──────────┬──────────────┘
           ↓
     Process request
           ↓
┌─────────────────────────┐
│ Response Middleware     │
│ - Log request.finish    │
│ - Capture response      │
│ - Write per-request JSON│
└──────────┬──────────────┘
           ↓
    Response sent

Exception occurs
    ↓
┌─────────────────────────┐
│ Exception Handler       │
│ - Log full traceback    │
│ - Write error JSON      │
│ - Return 500 response   │
└─────────────────────────┘
```

### **Log Files:**

- `app.log` - All requests, rotating 10MB
- `requests/{id}.json` - Per-request details
- `errors/{id}.json` - Exception details

---

## **Slide 17: Validation & Quality Assurance**

### Ensuring Correctness

### **Validation Layers:**

1. **Frontend Validation**

   - Real-time input checks
   - Range validation (200-3000mm)
   - Required field checks
   - Visual feedback (red outline)

2. **Pydantic Schema Validation**

   - Type validation
   - Required fields
   - Value constraints

3. **Geometry Validation**

   - `tools/validator.py` - Comprehensive checks
   - Frame integrity
   - Cutout containment
   - Hole position validation

4. **DXF Validation**
   - Pre-generation schema check
   - Abort if validation fails
   - Prevents invalid DXF output

### **Test Cases:**

- `Door TestCases/` - JSON test fixtures
- Single Normal, Single Fire (3 variants)
- Double Normal, Double Fire (2 variants)
- Input/Output validation pairs

### **Validation Report:**

```json
{
  "validation_passed": true/false,
  "errors": [],
  "warnings": [],
  "door_info": {...},
  "geometry_summary": {...}
}
```

---

## **Slide 18: Performance Optimization**

### Scalability Considerations

### **Current Optimizations:**

1. **Async Framework (FastAPI)**

   - Non-blocking I/O
   - Concurrent request handling
   - Background task support

2. **Thread Offloading**

   - DXF generation runs in thread pool
   - Prevents blocking event loop
   - `asyncio.to_thread()`

3. **Efficient Geometry Calculation**

   - Minimal coordinate transformations
   - Single-pass normalization
   - Lazy evaluation where possible

4. **Logging Optimization**
   - Body capture only for text (not binary)
   - Size limits (5MB cap)
   - Per-request files for parallelism

### **Performance Metrics:**

| Operation        | Time    | Notes                         |
| ---------------- | ------- | ----------------------------- |
| Single DXF       | < 2s    | Includes geometry + DXF write |
| PDF export       | +1-2s   | matplotlib conversion         |
| Batch (10 doors) | ~10s    | Depends on packing complexity |
| Preview geometry | < 500ms | No file I/O                   |

### **Bottlenecks:**

- Bin packing (O(n²) for complex layouts)
- PDF export (matplotlib initialization)
- Large Excel files (pandas parsing)

### **Future Optimizations:**

- Caching for repeated calculations
- Parallel DXF generation in batch mode
- Pre-warmed matplotlib backend

---

## **Slide 19: Security Features**

### Protection Mechanisms

### **Security Layers:**

1. **IP Whitelisting**

   - CIDR-based filtering
   - `ALLOWED_IPS` env variable
   - Early rejection (403 Forbidden)

2. **Authentication System**

   - Token-based (UUID)
   - HTTP-only cookies (XSS protection)
   - Hashed cookie values
   - Status management (active/inactive)

3. **Input Validation**

   - Pydantic type checking
   - Range validation
   - SQL injection prevention (no DB queries)

4. **File Upload Safety**

   - Temporary file handling
   - Extension validation (.xlsx/.xlsm)
   - Cleanup after processing

5. **CORS Configuration**

   - Currently open (`allow_origins=["*"]`)
   - **Recommendation:** Restrict in production

6. **Request Logging**
   - Full audit trail
   - Client IP tracking
   - User identification (X-User-ID header)

### **Security Checklist for Production:**

- ✅ Enable `REQUIRE_AUTH`
- ✅ Set `ALLOWED_IPS` to trusted networks
- ✅ Restrict CORS origins
- ✅ Use HTTPS (reverse proxy)
- ✅ Regular log review
- ✅ File cleanup monitoring

---

## **Slide 20: Future Enhancements**

### Roadmap & Improvements

### **Planned Features:**

1. **Database Integration**

   - Replace file-based user storage
   - PostgreSQL/SQLite
   - Door design library

2. **Advanced Packing**

   - Genetic algorithms for optimization
   - Custom constraints (spacing, orientation)
   - Visual packing preview

3. **Real-time Collaboration**

   - WebSocket support
   - Live preview updates
   - Multi-user sessions

4. **3D Visualization**

   - Three.js frontend
   - Interactive door preview
   - STL export

5. **Cloud Storage**

   - S3/Azure Blob integration
   - Generated file archiving
   - Long-term storage

6. **API Enhancements**

   - GraphQL endpoint
   - Webhook notifications
   - Batch status tracking

7. **UI Improvements**

   - React/Vue migration
   - Drag-and-drop Excel upload
   - In-browser DXF viewer

8. **Performance**
   - Redis caching
   - Background job queue (Celery)
   - CDN for static assets

---

## **Slide 21: Key Takeaways**

### Summary

### **Strengths:**

✅ **Modular Architecture** - Clean separation of concerns  
✅ **Type Safety** - Pydantic schemas throughout  
✅ **Dual Mode** - Single + Batch processing  
✅ **CAD-Ready Output** - Professional DXF/PDF files  
✅ **Bin Packing** - Automated material optimization  
✅ **Comprehensive Logging** - Full audit trail  
✅ **Optional Security** - IP whitelist + authentication

### **Technical Highlights:**

- **Async/Await** for scalability
- **Geometry pipeline** with 9 stages
- **Annotation system** (dimensions, notes, labels)
- **PDF export** capability
- **Excel integration** for batch workflows
- **Validation framework** ensures correctness

### **Business Value:**

- **Automation** - Replaces manual CAD work
- **Accuracy** - Eliminates human error
- **Speed** - Seconds vs hours
- **Scalability** - Handles bulk orders
- **Cost Reduction** - Minimal manual labor

---

## **Slide 22: Demo Scenarios**

### Live Walkthrough Examples

### **Scenario 1: Single Normal Door**

- **Input:** Width=600mm, Height=1105mm, Standard allowances
- **Output:** Single DXF with dimensions
- **Time:** ~1.5 seconds

### **Scenario 2: Fire Door with Glass**

- **Input:** Single Fire, Top-Fixed option, Custom glass position
- **Output:** DXF with glass cutouts + annotations
- **Time:** ~2 seconds

### **Scenario 3: Double Door**

- **Input:** Width=1200mm, Height=1700mm, Double category
- **Output:** Left + Right door frames in single DXF
- **Time:** ~2 seconds

### **Scenario 4: Batch Processing**

- **Input:** Excel file with 15 doors (various sizes)
- **Output:** ZIP with 2 sheet DXFs (optimally packed)
- **Time:** ~12 seconds

### **Scenario 5: Preview Mode**

- **Input:** Same as Scenario 1
- **Output:** JSON geometry (no file generation)
- **Time:** ~300ms

---

## **Slide 23: Architecture Decisions**

### Design Rationale

| Decision                | Rationale                        | Trade-off                           |
| ----------------------- | -------------------------------- | ----------------------------------- |
| **FastAPI**             | Modern, async, auto-docs         | Learning curve vs Flask             |
| **Pydantic**            | Type safety, validation          | Verbosity                           |
| **ezdxf**               | Pure Python, no CAD dependencies | Limited features vs commercial libs |
| **File-based auth**     | Simple, no DB required           | Not scalable to 1000s users         |
| **Vanilla JS frontend** | No build step, simple            | Less maintainable than React        |
| **rectpack**            | Battle-tested, efficient         | Limited customization               |
| **Monolithic repo**     | Easy deployment, single codebase | Harder to scale independently       |
| **JSON logging**        | Machine-readable, structured     | Larger file sizes                   |

### **When to Refactor:**

- **Users > 100:** Migrate auth to database
- **Requests > 1000/min:** Add caching layer
- **UI complexity grows:** Migrate to React/Vue
- **Team grows:** Split into microservices

---

## **Slide 24: Questions & Resources**

### **Q&A**

Common questions:

- **Q:** Can I customize annotation styles?  
  **A:** Yes, edit `annotation_styles.json`

- **Q:** Maximum batch size?  
  **A:** Tested up to 100 doors, limited by memory/CPU

- **Q:** Supported DXF version?  
  **A:** R2010 (AutoCAD 2010+)

- **Q:** Can I run without authentication?  
  **A:** Yes, default is no auth required

- **Q:** How to add new door types?  
  **A:** Extend Pydantic schemas + geometry functions

### **Resources:**

- **Repository:** (your GitHub URL)
- **Documentation:** See `*.md` files in repo
  - `QUICKSTART_AUTH.md`
  - `AUTH_IMPLEMENTATION.md`
  - `DEPLOYMENT_GUIDE.md`
- **API Docs:** `http://localhost:8000/docs` (FastAPI auto-docs)
- **Contact:** (your email/contact)

---

## **Slide 25: Thank You**

### DoorDesignPython

**Automated CAD Generation System**

**Developed by: Jinesh 🧠**

---

### **Technical Stack Summary:**

- Python 3.9+ | FastAPI | ezdxf
- Pydantic | pandas | rectpack
- HTML/CSS/JavaScript

### **Key Numbers:**

- **9** Geometry pipeline stages
- **5** REST API endpoints
- **< 2s** Average single door generation
- **15+** Test cases validated

### **Status:** ✅ Production Ready

---

## **Appendix: Diagram Source Files**

### **For PowerPoint Creation:**

1. **Architecture Diagrams:** Use draw.io, Lucidchart, or PowerPoint SmartArt
2. **Flow Diagrams:** Copy ASCII diagrams from this document, convert to visual
3. **Icons:** Use Font Awesome or PowerPoint built-in icons
4. **Color Scheme:**
   - Primary: #2563eb (blue)
   - Success: #16a34a (green)
   - Error: #dc2626 (red)
   - Background: #f8fafc (light gray)
   - Text: #1e293b (dark gray)

### **Suggested Slide Animations:**

- **Title slides:** Fade in
- **Diagrams:** Appear with connectors (sequential)
- **Lists:** Fly in from left (one by one)
- **Code blocks:** None (keep static for readability)

### **Fonts:**

- **Headings:** Segoe UI Bold / Arial Bold
- **Body:** Segoe UI / Arial
- **Code:** Consolas / Courier New (monospace)
