# Skern Garment Authentication System

## Table of Contents

1. **Core Principle** - Why QR codes alone provide zero security and how context-based verification works
2. **Two Entry Paths** - External camera scan vs. direct in-app scan flows
3. **Device Requirements** - Mobile-only enforcement, camera constraints, and resolution thresholds
4. **Tag Design** - QR code with guilloche + grid underlay, 4-quadrant structure
5. **Permissions Requested** - Camera, location, and motion/orientation requirements
6. **Scanning UX** - Progressive adaptive flow from full tag to conditional quadrant scans
7. **Data Captured at Scan Time** - Comprehensive device, GPS, motion, and camera metadata
8. **Data Sent to Server** - Complete payload structure for verification
9. **Authentication Processing Pipeline** - 10-step verification with fraud scenario coverage
10. **POPIA Compliance** - What can be stored, processed, and must be purged under SA law
11. **Fraud Scenarios Covered** - How each attack vector is prevented
12. **Summary** - Production-ready security architecture overview

---

## Core Principle

QR codes provide zero security. Security comes from verifying the scan occurs **physically on the real garment, right now**, in South Africa, using live context data: GPS, timestamp, device signals, camera behavior, motion sensors, and visual underlay analysis.

The system proves:

- Live handheld camera on flexible fabric (not photo/video/proxy)
- Real mobile device (not bot/emulator)
- Physical presence in South Africa
- Original printed tag (not counterfeit/reprint)
- Legitimate usage pattern (not abuse/duplicates)

---

## Two Entry Paths

### Path 1: External Camera Scan (Most Common)

1. User scans QR with phone camera app or Google Lens
2. Redirects to `/verify?id=CERT-12345`
3. Page loads → **Immediately request all permissions** (camera + location + motion on iOS)
4. User must **scan again in-app** to capture fresh GPS + timestamp + metadata
5. Send all data to server for verification

**Why re-scan?** External camera doesn't capture GPS/timestamp/metadata. Need fresh context data.

---

### Path 2: Direct In-App Scan

1. User navigates to `/verify` (no ID in URL)
2. User taps "Verify Garment" button
3. Request permissions (camera + location + motion on iOS)
4. Camera opens → User scans QR code
5. Capture: QR data + GPS + timestamp + metadata + underlay frames
6. Send to server for verification

---

## Device Requirements

**MOBILE ONLY - Desktop/PC/Emulator blocked:**

- Must be mobile device (phone/tablet)
- Must have rear camera with high resolution
- Torch/flashlight auto-enabled if available
- Touch input required

**Mobile-Only Enforcement (Early Reject):**

Perform before any permissions or processing.

**Algorithmic checks:**

- Verify touch capability (must support `maxTouchPoints > 0`)
- Analyze user-agent string for mobile indicators (e.g., "Mobile", "Android", "iPhone") and absence of desktop flags
- Cross-reference secondary signals (hardware core count, platform type)

**If any fail:** Immediate reject with message "Verification requires a mobile phone — desktops and emulators not supported."

---

**Camera Constraints:**

```typescript
constraints: {
  facingMode: { exact: "environment" },  // Rear camera ONLY
  width: { ideal: 4096 },                 // Request highest available
  height: { ideal: 4096 },                // Browser negotiates best
  advanced: [{ torch: true }]             // Auto-enable flashlight
}
```

---

**Post-Initialization Checks (After Camera Stream Starts):**

Query the actual granted camera settings:

- Retrieve exact resolution (width × height) provided by OS/browser
- Confirm `facingMode === "environment"` (rear camera)
- Evaluate granted resolution against thresholds

**Resolution Floor Rules:**

1. **Hard Reject if width OR height < 1280 pixels**

   - Reason: Insufficient detail for reliable guilloche/grid/underlay analysis
   - Message: "Rear camera resolution too low for secure verification — please use a device with a higher-resolution camera."

2. **Adaptive Mode for 1280–1920 range (rare on target market):**

   - Trigger enhanced UX guidance ("Hold very close to the tag")
   - Extended capture duration (7-8 seconds vs 5 seconds)
   - Server applies looser distortion/variance thresholds
   - Heavier reliance on motion correlation (Android) and pose/size change
   - May trigger additional quadrant close-ups if needed

3. **Standard Mode for ≥1920 resolution:**
   - Normal 5-second guided scan
   - Full precision analysis
   - Covers 95%+ of South African market (mid-range+ phones)

**If hard reject triggered:** Halt flow with clear message

**Forward actual granted resolution to server** for adaptive analysis (adjust thresholds based on pixel density, leverage motion correlation more on lower-res Android scans)

**Benefits:**

- Ensures sharp, well-lit frames for elite underlay detection
- Strong fraud signal (unusually low resolutions flag emulators/proxies)
- Balances SA market accessibility with security
- Matches brand positioning (mid-range+ garment buyers have capable phones)

---

## Tag Design: QR with Guilloche + Grid Underlay

Every Skern garment tag includes:

- **Standard QR code** (high error correction)
- **Integrated underlay patterns:**
  - Faint guilloche curved patterns (primary anti-counterfeit)
  - Straight grid lines (pose unwarping + rigidity detection)
  - Corner calibration marks (homography calculation)

**Security Features:**

- Guilloche curves provide copy-proofing and fabric distortion sensitivity
- Grid enables precise pose estimation and fake detection
- Printed via sublimation heat transfer (preserves fine details)
- Unique per certificateId (vary curve frequency/amplitude)

---

## Permissions Requested

**Required Permissions:**

1. **Camera** - Rear camera access for QR scanning and underlay analysis
2. **Location (High Accuracy)** - GPS coordinates to verify physical presence in South Africa
3. **Motion & Orientation (iOS only)** - DeviceMotionEvent and DeviceOrientationEvent require explicit permission on iOS 13+

**Permission Flow:**

- Location: Requested immediately on page interaction
- Camera: Requested when scan starts
- Motion/Orientation (iOS): Requested after other permissions granted

**Reject verification if any required permission denied.**

---

## Scanning UX (Progressive Adaptive Flow)

**Goal:** Natural, non-tedious scan that adapts based on device capability and data quality

### Progressive Scanning Strategy

**Phase 1: Full Tag Alignment (All Devices)**

1. Camera opens with overlay
2. Corner brackets + full frame outline
3. Text: "Align the entire tag within the guides"
4. Real-time green feedback when QR + anchors + guilloche/grid detected
5. Duration: 1-3 seconds until aligned

**Phase 2: Silent Frame Size Adjustment (All Devices)**

- Once aligned, text changes: "Perfect — now move closer to fill the frame"
- Frame guide silently shrinks (box gets smaller)
- User naturally moves closer
- System captures multiple frames during this movement
- Duration: 3-5 seconds
- **Captures:** Size variation (15-40%), multiple underlay samples, natural motion

**Phase 3: Conditional Quadrant Scan (If Needed)**

**Trigger conditions:**

- Low resolution device (1280-1920 range), OR
- Insufficient guilloche/grid data quality from Phases 1-2

**If triggered - Single Quadrant:**

- Text: "Please move so that the [top-left/bottom-right] marker is centered, then move closer until we say okay"
- Overlay highlights target quadrant with visual marker
- User centers that quadrant and moves closer
- System captures detailed frames of that specific quadrant
- Duration: 3-4 seconds
- Auto-advances when sufficient data captured

**If still insufficient (rare) - Second Quadrant:**

- Only on low-res devices (< 1920) or very poor initial capture
- Text: "One more section — center the [opposite quadrant] marker"
- Same process for second quadrant
- Duration: 3-4 seconds

**Total scan time:**

- **Standard flow (95% of users):** 5-8 seconds (Phases 1-2 only)
- **Low-res adaptive:** 8-12 seconds (Phases 1-2 + one quadrant)
- **Maximum fallback:** 12-16 seconds (Phases 1-2 + two quadrants)

### Real-Time Feedback

- Green checkmarks appear as each phase completes
- Progress indicator shows "Analyzing patterns..." during processing
- Smooth transitions between phases (feels like natural guidance, not separate steps)

**Success:** "Authentic garment verified!" with certificate details

---

## Data Captured at Scan Time

### Guaranteed Available (100% of devices)

- `navigator.userAgent` - device/browser identification
- `navigator.platform` - operating system
- `navigator.language` - device language
- `navigator.maxTouchPoints` - touch capability
- `window.innerWidth` x `window.innerHeight` - viewport size
- `screen.width` x `screen.height` - screen resolution
- `screen.colorDepth` - color depth
- `window.devicePixelRatio` - pixel density
- `screen.orientation.type` - portrait/landscape
- `screen.orientation.angle` - rotation angle
- `Date.now()` - timestamp
- `new Date().getTimezoneOffset()` - timezone offset
- Touch event detection - confirms mobile device

### High Availability (90%+ devices)

- `navigator.hardwareConcurrency` - CPU cores
- `navigator.connection.effectiveType` - network type (4g, 5g)
- GPS data (latitude, longitude, accuracy, altitude, heading, speed)
- Camera metadata (resolution used, torch status)

### iOS-Specific (requires permission)

- `DeviceMotionEvent` - accelerometer (x, y, z acceleration)
- `DeviceOrientationEvent` - gyroscope (alpha, beta, gamma rotation)

### Additional Scan Data

- Multiple high-res frames (for underlay analysis)
- Pose estimates (distance, angle, distortion metrics)
- Frame-to-frame size variation
- Scan duration and timing

---

## Data Sent to Server

**Complete Payload:**

```typescript
{
  certificateId: string,           // From QR code or URL
  qrData: string,                   // Raw QR data

  // GPS (captured at scan time)
  gps: {
    latitude: number,
    longitude: number,
    accuracy: number,
    altitude: number | null,
    altitudeAccuracy: number | null,
    heading: number | null,
    speed: number | null
  },

  // Timestamp
  timestamp: string,                // ISO format

  // Device metadata (100% available)
  device: {
    userAgent: string,
    platform: string,
    language: string,
    maxTouchPoints: number,
    hardwareConcurrency: number | null,
    deviceMemory: number | null
  },

  // Display metadata
  display: {
    screenWidth: number,
    screenHeight: number,
    viewportWidth: number,
    viewportHeight: number,
    colorDepth: number,
    pixelRatio: number
  },

  // Orientation
  orientation: {
    type: string,
    angle: number
  },

  // Network
  network: {
    effectiveType: string | null,
    downlink: number | null,
    rtt: number | null
  },

  // Motion & orientation (iOS with permission)
  motion: {
    acceleration: { x, y, z } | null,
    rotationRate: { alpha, beta, gamma } | null
  } | null,

  // Camera metadata
  camera: {
    facingMode: string,              // Must be "environment"
    resolution: { width, height },
    torchEnabled: boolean
  },

  // Timing & behavior
  timing: {
    pageLoadToScan: number,
    scanDuration: number,             // Should be ≥5 seconds
    sizeVariation: number             // % change during scan
  },

  // Underlay analysis frames
  frames: Array<{
    timestamp: number,
    imageData: string,                // Base64 high-res frame
    poseEstimate: {
      distance: number,
      angle: number,
      distortion: number
    }
  }>
}
```

---

## Authentication Processing Pipeline

**Sequential checks with early exit** — fast for legitimate scans (~1-2s after 5s capture)

### Step 1: Basic Decode & Camera Validation

**Detects:** Wrong camera, proxy attempt

- Verify QR decodes successfully
- Confirm `facingMode === "environment"`
- **Reject if:** No decode or wrong camera

---

### Step 2: Timing & Basic Liveness

**Fraud Scenario 1:** Proxy/Photo/Screenshot (no real movement)

- Require scan duration ≥5 seconds with live camera
- Measure apparent size change during silent frame adjustment
- **Require:** ≥15-40% size variation
- **Reject if:** Too short or static frames

---

### Step 3: Underlay Calibration & Grid Detection

**Fraud Scenario 7:** Counterfeit/Rigid Fake (missing/degraded pattern)

- Detect corner marks in frames
- Identify guilloche curves and grid lines
- **Require:** Pattern detected in ≥90% of frames
- Compute homography for unwarping
- **Reject if:** Poor detection or missing patterns

---

### Step 4: Fabric Distortion Check

**Fraud Scenario 7:** Rigid flat fake (paper/cardboard print)

- Measure guilloche curve curvature variation
- Analyze grid spacing variation across frames
- **Require:** Natural organic flex (≥5-10% variation from breathing/hand movement)
- **Reject if:** Too perfectly straight or static (indicates rigid surface)

---

### Step 5: Guilloche Pattern Integrity

**Fraud Scenario 7:** Reprint/counterfeit (degraded quality)

- In unwarped regions: measure line thickness, continuity, variance
- Compare against genuine sublimation printing range
- **Reject if:** Degraded patterns (low variance, breaks, wrong thickness)

---

### Step 6: Motion Sensor Correlation

**Fraud Scenario 1:** Proxy/Video Feed (mismatched movement)

- Compare accelerometer/gyroscope data with visual pose changes
- Use unwarped grid for precise pose estimation
- **Require:** Strong correlation during frame adjustment
- **Reject if:** Sensors static or mismatched with visual movement

---

### Step 7: Emulator/Bot Detection

**Fraud Scenario 3:** Automated/non-human scanning

Score from: `maxTouchPoints`, `userAgent`, `hardwareConcurrency`, motion sensors, timing patterns

**Response tiers:**

- **Low score:** Proceed normally
- **Medium score:** Light challenge (verify color/size from photos)
- **High score:** Medium challenge (verify style details)
- **99%+ score:** Heavy challenge (purchase date/location) or reject

---

### Step 8: Location Validation

**Fraud Scenario 2 & 6:** GPS spoofing / Shared photo across distances

- **Require:** GPS coordinates within South Africa bounds
- **Impossible travel check:** Compare with previous scans
  - Calculate distance and time between scans
  - **Reject if:** Speed >200-500 kph (indicates location spoofing or impossible travel)

---

### Step 9: Duplicate/Abuse Prevention

**Fraud Scenario 5:** Mass scans/sharing/automation

**Per-device limits:**

- 3 scans per device → 10-minute cooldown
- Unlimited unique devices allowed (encourages legitimate sharing)

**Per-certificate monitoring:**

- High velocity (>20-30 scans) → Flag for review
- First scan records origin (timestamp + location)
- Future scans display: "First verified on [date] at [location]"

---

### Step 10: Final Approval

**All checks passed:**

- Return: "Authentic garment verified!"
- Display certificate details
- Show first scan origin info
- Log verification with all context data

---

## POPIA Compliance (South Africa)

**Protection of Personal Information Act (POPIA) - What we can STORE:**

### ✅ Allowed to Store (Required for Garment Verification)

- Certificate ID
- Verification result (authentic/fake)
- Timestamp (date/time of scan)
- **Precise GPS coordinates** (latitude/longitude within 5 meters) - **Required for fraud prevention**
- GPS accuracy value
- Device type category (iOS/Android, NOT specific model)
- Screen resolution category (small/medium/large)
- Verification status history
- Scan count per certificate
- Timezone offset
- Orientation type (portrait/landscape)
- Network type (WiFi/4G/5G)
- First scan origin (timestamp + location for certificate activation)

**Legal Basis for Storing Precise Location:**

- Legitimate interest in fraud prevention
- Necessary for contract performance (verification service)
- User consents to location access for verification purpose
- Location tied to garment verification, not personal tracking
- Required to detect impossible travel patterns

### ⚠️ Process but DON'T Store (Used for verification only)

- Full device fingerprint (userAgent, platform details)
- IP address
- Raw accelerometer/gyroscope data
- Camera metadata (specific resolution)
- Hardware details (CPU cores, RAM)
- Battery information
- Precise timing data
- Touch patterns
- Raw underlay analysis frames

### ❌ Never Capture or Store (POPIA Prohibited)

- User identity without explicit consent
- Biometric data (face scans, fingerprints)
- Personal communications
- Contacts or calendar data
- Photos/media from device (beyond verification frames)
- Browsing history
- Any data that can identify an individual beyond the verification event

### Data Retention Rules

- **Verification logs with precise location**: 2 years maximum (fraud investigation window)
- **Certificate scan history**: Full record maintained for garment lifecycle
- **Location data**: Stored with timestamp for audit trail and impossible travel detection
- **Device metadata**: Generate hash, store hash only, discard raw data
- **Underlay frames**: Processed and discarded immediately after verification

### User Rights Under POPIA

- Right to know what data is collected (disclosed in consent dialog)
- Right to access their verification history
- Right to deletion after retention period
- Right to object to processing (but prevents verification)
- Must provide clear privacy policy explaining location storage

### Implementation Strategy

1. **Capture** comprehensive data for verification
2. **Verify** using all available context and underlay analysis
3. **Store** precise location + timestamp (fraud prevention)
4. **Hash/Anonymize** device-identifying fields
5. **Purge** raw frames and extra metadata immediately after verification

**Example Storage:**

```json
{
  "certificateId": "CERT-12345",
  "verificationResult": "authentic",
  "timestamp": "2024-01-08T14:23:45Z",
  "location": {
    "latitude": -26.123456,
    "longitude": 28.56789,
    "accuracy": 4.2,
    "verified": true
  },
  "firstScan": {
    "timestamp": "2024-01-08T14:23:45Z",
    "location": "Johannesburg, Gauteng"
  },
  "deviceTypeHash": "sha256(...)",
  "screenCategory": "large",
  "scanCount": 1,
  "fraudScore": 0.02,
  "underlayPassed": true
}
```

---

## Fraud Scenarios Covered

### Scenario 1: Proxy/Photo/Video Feed

**Protection:** Steps 2 & 6 — Extreme liveness (5s + size variation) + motion sensor correlation

### Scenario 2: GPS Spoofing

**Protection:** Step 8 — South Africa bounds + cross-reference timezone

### Scenario 3: Bot/Emulator

**Protection:** Step 7 — Tiered database challenges based on detection score

### Scenario 5: Mass Scans/Duplicates

**Protection:** Step 9 — Permissive but throttled (3 per device, cooldown)

### Scenario 6: Impossible Travel

**Protection:** Step 8 — Speed calculation between scans (>200-500 kph = reject)

### Scenario 7: Physical Counterfeit/Reprint

**Protection:** Steps 3-5 — Guilloche/grid underlay analysis + fabric distortion + first-scan activation

---

## Summary

This system provides **banknote-level physical security + digital liveness**:

✅ **Fast UX** - 5-second natural scan with real-time guidance
✅ **POPIA-compliant** - Store only what's necessary, 2-year retention
✅ **In-house production** - Works with your sublimation printing setup
✅ **All fraud paths closed** - Legitimate users verify effortlessly, attackers fail hard

**Security layers:**

- Physical: Guilloche + grid underlay (unique, fabric-sensitive, counterfeit-resistant)
- Digital: GPS + motion sensors + timing + device fingerprinting
- Behavioral: Natural movement requirements + anti-automation challenges
- Network: Location validation + impossible travel detection + abuse throttling

Production-ready for Skern garment authentication.
