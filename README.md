# ADP Resume Downloader - LangGraph Implementation

Enterprise-grade automation system for bulk downloading candidate resume PDFs from ADP Workforce Now. Built with LangGraph state machine architecture for reliable workflow orchestration and Playwright for robust browser automation.

## 🚀 Quick Start

### 1. Setup

```bash
cd langgraph
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
playwright install
```

### 2. Configuration

Edit `.env` with your ADP credentials:
```env
ADP_USERNAME=your_username
ADP_PASSWORD=your_password
ADP_LOGIN_URL=https://your-company.adp.com/workforce-now/login
```

### 3. Run

```bash
python main.py
```

## 📁 Architecture & Components

### Core Modules

#### `main.py` - Application Entry Point
- **Purpose**: Orchestrates the complete workflow execution
- **Implementation**: Initializes workflow state using Pydantic models, invokes LangGraph workflow, handles graceful shutdown and error reporting
- **Key Features**: Windows async event loop configuration, comprehensive logging setup, statistics collection and reporting

#### `workflow.py` - LangGraph State Machine
- **Purpose**: Defines the automated workflow as a directed graph of execution nodes
- **Implementation**: Uses LangGraph's StateGraph to create a fault-tolerant state machine with conditional transitions
- **Workflow Nodes**: 
  - `setup_browser_node`: Browser initialization and configuration
  - `login_node`: Authentication handling with multiple selector strategies
  - `navigate_to_candidates_node`: Intelligent navigation to candidate listings
  - `extract_candidates_node`: Multi-page candidate data extraction with pagination
  - `download_resumes_node`: Parallel PDF download orchestration
  - `cleanup_node`: Resource cleanup and final state determination
- **State Management**: Maintains workflow state across nodes, handles error propagation, manages conditional branching logic

#### `browser.py` - Web Automation Engine
- **Purpose**: Encapsulates all browser interactions using Playwright automation framework
- **Implementation**: Async context management for browser lifecycle, multiple selector strategies for cross-instance compatibility
- **Authentication Logic**: 
  - Multiple username/password field selector patterns
  - Dynamic form submission detection
  - Post-login navigation validation
- **Navigation Strategy**: 
  - Pattern-based menu item detection
  - URL analysis for candidate page identification
  - Fallback navigation methods
- **Data Extraction**: 
  - CSS selector arrays for candidate element detection
  - Profile link extraction and URL normalization
  - Pagination detection and traversal

#### `downloader.py` - Parallel Download Manager
- **Purpose**: Manages concurrent PDF downloads with reliability and performance optimization
- **Implementation**: 
  - AsyncIO semaphore-based concurrency control
  - aiohttp session pooling for connection reuse
  - Async file I/O with aiofiles for non-blocking operations
- **Download Process**:
  - Resume URL detection using multiple selector patterns
  - HTTP response validation and error handling
  - File integrity validation (PDF header verification)
  - Safe filename generation with conflict resolution
- **Error Handling**: Individual download failure isolation, automatic retry logic, download attempt tracking

#### `config.py` - Configuration Management
- **Purpose**: Centralized configuration using environment variables and Pydantic validation
- **Implementation**: Type-safe configuration models with default values, environment variable loading with python-dotenv
- **Configuration Domains**:
  - ADP authentication credentials
  - Browser automation settings (headless mode, timeouts)
  - Download parameters (concurrency, file paths, retry limits)
  - Extraction limits (page counts, delays)
- **Logging Setup**: Structured logging configuration with file and console output, configurable log levels

#### `models.py` - Type-Safe Data Models
- **Purpose**: Defines all data structures using Pydantic for validation and serialization
- **Implementation**: Enum-based state definitions for type safety, BaseModel classes with validation logic
- **Core Models**:
  - `WorkflowGraphState`: TypedDict for LangGraph state management
  - `CandidateModel`: Individual candidate data with processing status
  - `WorkflowStats`: Performance metrics and statistics tracking
  - `BrowserState`: Browser session state and error tracking
- **State Enums**: Workflow progression states, login result types, download status classifications

## ⚙️ Technical Implementation Details

### LangGraph Workflow Architecture
- **State Machine Design**: Implements a directed acyclic graph (DAG) where each node represents a specific operation
- **Conditional Branching**: Uses predicate functions to determine next node execution based on current state
- **Error Recovery**: Built-in error propagation with cleanup guarantees regardless of failure point
- **State Persistence**: Maintains complete workflow state across all nodes for debugging and recovery

### Browser Automation Strategy
- **Playwright Integration**: Leverages Playwright's cross-browser automation with Chromium backend
- **Selector Resilience**: Multiple CSS selector patterns per element type to handle ADP instance variations
- **Network Optimization**: Configurable wait strategies (networkidle, domcontentloaded) for reliable page transitions
- **Context Management**: Isolated browser contexts prevent session conflicts and ensure clean state

### Parallel Processing Implementation
- **Semaphore-Based Concurrency**: AsyncIO semaphores limit simultaneous downloads to prevent server overload
- **Connection Pooling**: aiohttp session reuse reduces connection overhead and improves performance
- **Task Orchestration**: asyncio.gather with exception isolation ensures individual failures don't halt entire process
- **Memory Management**: Streaming downloads with async file operations prevent memory exhaustion on large files

### Data Validation & Integrity
- **Pydantic Schema Validation**: Runtime type checking and data validation for all models
- **PDF Verification**: Binary header validation ensures downloaded files are valid PDF documents
- **URL Normalization**: Relative to absolute URL conversion handles various ADP link formats
- **Filename Sanitization**: Character filtering and conflict resolution for safe filesystem operations

## 🔧 Configuration Parameters

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ADP_USERNAME` | string | required | ADP Workforce Now login username |
| `ADP_PASSWORD` | string | required | ADP Workforce Now login password |
| `ADP_LOGIN_URL` | string | required | Direct login URL for your ADP instance |
| `DOWNLOAD_MAX_CONCURRENT` | integer | 3 | Maximum simultaneous download connections |
| `DOWNLOAD_TIMEOUT_SECONDS` | integer | 120 | HTTP request timeout per download |
| `DOWNLOAD_MAX_RETRIES` | integer | 3 | Maximum retry attempts per failed download |
| `DOWNLOAD_FOLDER` | string | ./downloads | Local directory for saving PDF files |
| `BROWSER_HEADLESS` | boolean | false | Run browser without GUI (true/false) |
| `BROWSER_TIMEOUT_SECONDS` | integer | 30 | Page load timeout for browser operations |
| `EXTRACTION_MAX_PAGES` | integer | 50 | Maximum candidate listing pages to process |
| `EXTRACTION_DELAY_SECONDS` | integer | 2 | Delay between page requests (rate limiting) |

### Performance Tuning
- **Concurrency Scaling**: Increase `DOWNLOAD_MAX_CONCURRENT` for faster downloads (monitor server load)
- **Memory Usage**: Lower concurrency reduces memory footprint for large candidate sets
- **Rate Limiting**: Adjust `EXTRACTION_DELAY_SECONDS` to respect ADP server limits
- **Timeout Configuration**: Balance `BROWSER_TIMEOUT_SECONDS` between reliability and speed

## 📊 Output & Monitoring

### File Organization
- **Download Directory**: All PDFs saved to configured `DOWNLOAD_FOLDER` with timestamp-based organization
- **Filename Convention**: `{sanitized_candidate_name}.pdf` with automatic conflict resolution via numeric suffixes
- **File Validation**: Each download verified for PDF format integrity and minimum size thresholds

### Logging & Diagnostics
- **Structured Logging**: JSON-formatted logs with timestamp, level, and contextual information
- **Log Destinations**: Simultaneous console output and file logging (`resume_downloader.log`)
- **Progress Tracking**: Real-time candidate processing status with completion percentages
- **Error Classification**: Detailed error categorization (network, authentication, parsing, validation)

### Statistics & Reporting
- **Workflow Metrics**: Total execution time, candidates processed, success/failure rates
- **Download Analytics**: File sizes, download speeds, retry statistics
- **Performance Data**: Memory usage, network throughput, browser resource consumption
- **Final Summary**: Comprehensive report with actionable insights for optimization

## 🔍 Troubleshooting & Debugging

### Common Issues & Solutions

#### Authentication Failures
- **Symptom**: Login node fails, workflow terminates at authentication
- **Diagnosis**: Check `ADP_LOGIN_URL` format, verify credentials, examine browser console for CAPTCHA/MFA
- **Resolution**: Update selector patterns in `browser.py` login methods, ensure direct login URL (not landing page)

#### Navigation & Element Detection
- **Symptom**: No candidates found, extraction returns empty results
- **Diagnosis**: Browser automation cannot locate candidate elements on your ADP instance
- **Resolution**: Inspect ADP DOM structure, update CSS selectors in `candidate_selectors` array
- **Debug Mode**: Set `BROWSER_HEADLESS=false` to visually inspect navigation process

#### Download Failures
- **Symptom**: Candidates extracted but PDF downloads fail
- **Diagnosis**: Resume links not detected, download URLs invalid, or network issues
- **Resolution**: Verify PDF link selectors, check ADP permissions for resume access, monitor network logs

#### Performance & Memory Issues
- **Symptom**: Process hangs, excessive memory usage, or timeout errors
- **Diagnosis**: Too many concurrent operations or large candidate datasets
- **Resolution**: Reduce `DOWNLOAD_MAX_CONCURRENT`, increase timeout values, process in smaller batches

### Advanced Debugging Techniques

#### Browser Automation Debugging
```python
# Enable verbose Playwright logging
PLAYWRIGHT_BROWSERS_PATH=./browsers playwright install --with-deps
```

#### Network Traffic Analysis
```python
# Add to browser.py for request/response logging
await page.route("**/*", lambda route: print(f"Request: {route.request.url}"))
```

#### State Machine Visualization
```python
# Add workflow state logging
LOGGER.info(f"State transition: {previous_state} -> {current_state}")
```

## 🛠 Customization & Extension

### ADP Instance Adaptation

#### Selector Configuration
Modify `browser.py` to match your ADP instance's DOM structure:

```python
# Authentication selectors
username_selectors = [
    'input[name="username"]',          # Standard username field
    'input[name="loginId"]',           # Alternative field name
    '#your-custom-username-id',       # Instance-specific ID
    '.custom-username-class'          # Instance-specific class
]

# Candidate listing selectors
candidate_selectors = [
    '.candidate-row',                  # Standard candidate rows
    '.employee-listing-item',          # Alternative structure
    '[data-candidate-id]',            # Data attribute approach
    '.your-custom-candidate-class'    # Instance-specific selector
]

# Resume download selectors
download_selectors = [
    'a[href*="resume"]',              # Resume links
    'a[href*="cv"]',                  # CV links
    '.resume-download-button',        # Button-based downloads
    '[data-action="download-resume"]' # Data attribute triggers
]
```

#### Workflow Node Extension
Add custom processing nodes to the LangGraph workflow:

```python
# In workflow.py
async def custom_processing_node(self, state: WorkflowGraphState) -> WorkflowGraphState:
    # Custom logic here
    return state

# Register in create_workflow_graph()
workflow.add_node("custom_processing", orchestrator.custom_processing_node)
workflow.add_edge("extract_candidates", "custom_processing")
```

#### Data Model Extensions
Extend candidate models for additional data capture:

```python
# In models.py
class ExtendedCandidateModel(CandidateModel):
    department: Optional[str] = None
    hire_date: Optional[datetime] = None
    salary_range: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
```

### Integration Capabilities

#### Database Integration
```python
# Add database persistence
async def save_candidate_to_db(candidate: CandidateModel):
    # Database insertion logic
    pass
```

#### API Integration
```python
# Add REST API endpoints
from fastapi import FastAPI
app = FastAPI()

@app.post("/start-extraction")
async def trigger_workflow():
    # Workflow initiation logic
    pass
```

#### Notification Systems
```python
# Add status notifications
async def send_completion_notification(stats: WorkflowStats):
    # Email/Slack/Teams notification logic
    pass
```

## 🔐 Security & Compliance

### Data Protection
- **Credential Management**: Environment variable isolation prevents credential exposure in code
- **Memory Safety**: Sensitive data cleared from memory after use, no credential logging
- **File System Security**: Configurable download directories with proper permission management
- **Network Security**: HTTPS enforcement, certificate validation, secure session management

### Compliance Considerations
- **Access Control**: Verify user permissions for candidate data access before deployment
- **Data Retention**: Configure automatic cleanup of downloaded files per retention policies
- **Audit Logging**: Comprehensive activity logs for compliance and security monitoring
- **Rate Limiting**: Built-in delays prevent server overload and respect usage policies

### Production Deployment
- **Environment Isolation**: Separate configuration files for development/staging/production
- **Secret Management**: Integration with secure secret management systems (AWS Secrets Manager, Azure Key Vault)
- **Monitoring Integration**: Compatible with enterprise monitoring solutions (New Relic, DataDog)
- **Error Alerting**: Configurable failure notifications for production monitoring

---

**Security Notice**: This automation tool requires valid ADP Workforce Now credentials and appropriate access permissions. Ensure compliance with your organization's data access policies and applicable privacy regulations before deployment.
