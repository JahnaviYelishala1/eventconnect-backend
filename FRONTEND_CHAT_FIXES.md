# 🎯 ANDROID CHAT FIXES - KOTLIN

Your backend is now ready. **Frontend must implement these 8 fixes** to enable stable chat.

---

## 🎯 ROOT CAUSE

* **Stale Firebase token** → WebSocket closes immediately
* **UI blocking** → Chat screen stuck in loader
* **Wrong message alignment** → Sender ID mismatch

---

## ✅ FIXES REQUIRED IN KOTLIN

### 1️⃣ FIX TOKEN (CRITICAL - MOST IMPORTANT)

**Location:** `ChatViewModel.kt`

**REMOVE THIS:**
```kotlin
val authHeader = getAuthHeader() ?: return@launch
val token = authHeader.removePrefix("Bearer ").trim()
```

**REPLACE WITH:**
```kotlin
val firebaseUser = FirebaseAuth.getInstance().currentUser ?: return@launch
val token = firebaseUser.getIdToken(true).await().token ?: return@launch
```

**Why:** 
- `getIdToken(true)` forces Firebase to refresh the token
- Never cache tokens; always request fresh ones
- `clock_skew_seconds=60` on backend will handle minor timing drift

**CRITICAL:** `getIdToken(true)` - the `true` parameter FORCES refresh.

---

### 2️⃣ PREVENT UI FREEZE

**Location:** `ChatScreen.kt`

**REMOVE THIS:**
```kotlin
if (effectiveUserId == null || effectiveUserId == 0) {
    CircularProgressIndicator()
    return
}
```

**REPLACE WITH:**
```kotlin
if (effectiveUserId == null || effectiveUserId == 0) {
    Text("Loading chat...")
}
```

**Why:** `CircularProgressIndicator()` early returns and freezes the UI. `Text()` still renders, allowing WebSocket to eventually connect.

---

### 3️⃣ CONNECT SOCKET ONLY AFTER USER READY

**Location:** `ChatViewModel.kt` - before WebSocket creation

**ADD:**
```kotlin
if (currentUserId == null) return@launch
```

This ensures user ID is loaded from DB before attempting connection.

---

### 4️⃣ ADD DELAY TO PREVENT TIMING ISSUES

**Location:** `ChatViewModel.kt` - in connection coroutine

**BEFORE connecting WebSocket, add:**
```kotlin
delay(300)  // Allow token refresh and user load
```

This gives iOS/Android time to:
- Refresh Firebase token
- Load user from DB
- Prepare WebSocket

---

### 5️⃣ FIX MESSAGE ALIGNMENT (VERY IMPORTANT FOR UX)

**Location:** `ChatScreen.kt` - where messages are rendered

**BEFORE rendering Row, calculate:**
```kotlin
val isMe = msg.sender_id == effectiveUserId

Row(
    horizontalArrangement = 
        if (isMe) Arrangement.End else Arrangement.Start
) {
    Surface(
        color = if (isMe) Color(0xFF7B2FF2) else Color.White,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .padding(8.dp)
            .widthIn(max = 280.dp)
    ) {
        Text(msg.message, modifier = Modifier.padding(12.dp))
    }
}
```

**ADD DEBUG LOG:**
```kotlin
Log.d("CHAT_DEBUG", "ME=$effectiveUserId sender=${msg.sender_id}")
```

---

### 6️⃣ FIX WEBSOCKET URL

**Location:** `ChatWebSocketManager.kt` or wherever you create the URL

**ENSURE:**
```kotlin
val wsUrl = "wss://YOUR_NGROK_URL/api/chat/ws/$requestId?token=$token"
```

**Check:**
- Protocol is `wss://` (secure), NOT `ws://`
- Replace `YOUR_NGROK_URL` with actual ngrok URL
- Include `?token=$token` as query param
- Token should be the fresh Firebase token from step 1

---

### 7️⃣ ADD DEBUG LOGS

**Location:** `ChatWebSocketManager.kt`

**ADD:**
```kotlin
onOpen {
    Log.d("CHAT_WEBSOCKET", "CONNECTED requestId=$requestId")
}

onClosed {
    Log.d("CHAT_WEBSOCKET", "CLOSED requestId=$requestId")
}

onFailure { e ->
    Log.e("CHAT_WEBSOCKET", "FAILED: ${e.message}", e)
}

onMessage { text ->
    Log.d("CHAT_WEBSOCKET", "MESSAGE: $text")
}
```

---

### 8️⃣ ADD FAIL-SAFE SEND

**Location:** `ChatWebSocketManager.kt` - send function

**WRAP SEND:**
```kotlin
fun sendMessage(text: String) {
    if (webSocket == null) {
        Log.e("CHAT_SEND", "WebSocket not connected!")
        return
    }
    try {
        webSocket?.send(text)
        Log.d("CHAT_SEND", "Message sent: $text")
    } catch (e: Exception) {
        Log.e("CHAT_SEND", "Failed to send: ${e.message}", e)
    }
}
```

---

## 🧠 BACKEND STATUS ✅

All backend fixes are **COMPLETE**:

✅ Token validation with 60s clock skew
✅ Correct sender_role derivation
✅ Always sends sender_id + sender_role
✅ Only closes on invalid token / non-participant
✅ Comprehensive logging
✅ Correct participation logic
✅ Uses request_id (not booking_id) for chat

---

## 🔥 DEBUG CHECKLIST

### On App Start:

1. **Android Logs:**
   ```
   CHAT_WEBSOCKET: CONNECTED requestId=123
   CHAT_DEBUG: ME=42 sender=42
   ```

2. **Backend Logs:**
   ```
   Chat WS connected request_id=123 user_id=42 is_organizer=True
   Chat WS broadcast_ok request_id=123 user_id=42 role=event_organizer
   ```

3. **If Fails:**
   ```
   ANDROID: onFailure: Invalid auth header
   → Check token is fresh (use getIdToken(true))
   
   ANDROID: onClosed: code 1008
   → Check user_id is set before connect
   
   ANDROID: Message sender_id=0 vs ME=42
   → Check effectiveUserId is loaded correctly
   ```

---

## 📋 FINAL CHECKLIST

- [ ] Token uses `getIdToken(true)` (refresh every time)
- [ ] No `CircularProgressIndicator()` early return
- [ ] User ID checked before WebSocket creation
- [ ] 300ms delay before connecting
- [ ] Message alignment based on `sender_id == effectiveUserId`
- [ ] WebSocket URL has `wss://` and token query param
- [ ] Debug logs added in onOpen/onClosed/onFailure
- [ ] Send wrapped in try-catch with null check
- [ ] Logs show "CONNECTED" and "broadcast_ok"

---

## ✅ AFTER ALL FIXES

Expected behavior:

✔️ Chat opens instantly (no infinite loader)  
✔️ WebSocket stays connected (no instant close)  
✔️ Messages appear immediately  
✔️ Sender messages appear on right (blue)  
✔️ Receiver messages appear on left (white)  
✔️ No crashes  
✔️ Logs show clean connection + message flow  

---

## 🆘 TROUBLESHOOTING

| Issue | Fix |
|-------|-----|
| `Invalid auth header` | Use `getIdToken(true)` to refresh token |
| `WebSocket closes after connect` | Check `user_id` is loaded before connect |
| `Messages all on left side` | Check `effectiveUserId` vs `msg.sender_id` |
| `Infinite loader` | Remove early `CircularProgressIndicator()` return |
| `No messages appear` | Check `delay(300)` is there; check token is fresh |
| `sender_id=0` | Ensure user is authenticated before render |

---
