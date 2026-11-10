#include "ble.h"
#include "diag.h"
#include "esp_system.h"
// The boot's mode: a one-shot flag in RTC memory (survives the software reset, garbage after power-on). Read in
// bleInUse(), which Arduino's initArduino calls before setup: false = it releases the BT controller's memory to the heap.
RTC_NOINIT_ATTR static uint32_t fastBootMagic;
static const uint32_t FAST_BOOT_MAGIC = 0x66617374;
static int8_t bootBle = -1;   // decided once, at the first ask
static bool decideBle() {
  if (bootBle < 0) { bootBle = fastBootMagic == FAST_BOOT_MAGIC ? 0 : 1; fastBootMagic = 0; }
  return bootBle;
}
void ble_request_fast() { fastBootMagic = FAST_BOOT_MAGIC; diag_stage(DIAG_RESTART_REQ); delay(50); esp_restart(); }
#ifdef NO_BLE   // perf-baseline build (see tools/e2e.sh --no-ble): USB serial only
DualOut out;
bool ble_on() { return false; }
void ble_tick() {}
int ble_window_left_s() { return -1; }
void ble_init(const char *) {}
int ble_read() { return -1; }
size_t DualOut::write(uint8_t c) { return Serial.write(c); }
size_t DualOut::write(const uint8_t *buf, size_t n) { return Serial.write(buf, n); }
#else
#include <NimBLEDevice.h>

#define NUS_UUID    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_RX_UUID "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_TX_UUID "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

static NimBLECharacteristic *txChar = nullptr;
static volatile bool connected = false;
static uint8_t rxBuf[512];
static volatile uint16_t rxHead = 0, rxTail = 0;  // written on the NimBLE task, drained in loop()
static uint8_t txBuf[244];
static size_t txLen = 0;
static volatile uint16_t peerMtu = 23;
static volatile bool everConnected = false; static volatile uint32_t lastSeenMs = 0;   // the window (ble_tick)
// Arduino's hook (esp32-hal-bt.c, weak): BT memory stays reserved only on a boot that runs BLE.
extern "C" bool bleInUse(void) { return decideBle(); }
bool ble_on() { return decideBle(); }
int ble_window_left_s() {
  if (!ble_on() || connected) return -1;
  const uint32_t limit = everConnected ? BLE_GRACE_S * 1000u : BLE_WINDOW_S * 1000u, since = everConnected ? millis() - lastSeenMs : millis();
  return since >= limit ? 0 : (int)((limit - since + 999) / 1000);
}
void ble_tick() {
  if (!ble_on()) return;
  if (connected) { lastSeenMs = millis(); return; }
  if (ble_window_left_s() == 0) { Serial.println("ble: window over, rebooting into fast mode (BLE off)"); ble_request_fast(); }
}

static size_t txMax() { size_t m = peerMtu > 3 ? peerMtu - 3 : 20; return m < sizeof(txBuf) ? m : sizeof(txBuf); }

static void txFlush() {
  if (txLen && connected && txChar) { txChar->setValue(txBuf, txLen); txChar->notify(); }
  txLen = 0;
}

struct ServerCb : NimBLEServerCallbacks {
  void onConnect(NimBLEServer *, NimBLEConnInfo &ci) override { connected = true; peerMtu = ci.getMTU(); Serial.printf("ble: connect mtu %u\n", peerMtu); }
  void onDisconnect(NimBLEServer *, NimBLEConnInfo &, int reason) override {
    connected = false; txLen = 0; everConnected = true; lastSeenMs = millis();   // BLE_GRACE_S to come back
    Serial.printf("ble: disconnect %d\n", reason); NimBLEDevice::startAdvertising();
  }
  void onMTUChange(uint16_t mtu, NimBLEConnInfo &) override { peerMtu = mtu; Serial.printf("ble: mtu %u\n", mtu); }
};
struct RxCb : NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *c, NimBLEConnInfo &) override {
    std::string v = c->getValue();
    for (char ch : v) { uint16_t nx = (rxHead + 1) % sizeof(rxBuf); if (nx != rxTail) { rxBuf[rxHead] = ch; rxHead = nx; } }
  }
};

void ble_init(const char *name) {
  NimBLEDevice::init(name);
  NimBLEDevice::setMTU(247);
  NimBLEServer *srv = NimBLEDevice::createServer();
  srv->setCallbacks(new ServerCb());
  NimBLEService *svc = srv->createService(NUS_UUID);
  txChar = svc->createCharacteristic(NUS_TX_UUID, NIMBLE_PROPERTY::NOTIFY);
  NimBLECharacteristic *rx = svc->createCharacteristic(NUS_RX_UUID, NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  rx->setCallbacks(new RxCb());
  // Name + 128-bit UUID exceed the 31-byte adv packet: name in adv, UUID in scan response.
  NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
  NimBLEAdvertisementData advData, scanData;
  advData.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  advData.setName(name);
  scanData.setCompleteServices(NimBLEUUID(NUS_UUID));
  adv->setAdvertisementData(advData);
  adv->setScanResponseData(scanData);
  adv->start();
}

int ble_read() { if (rxHead == rxTail) return -1; uint8_t c = rxBuf[rxTail]; rxTail = (rxTail + 1) % sizeof(rxBuf); return c; }

DualOut out;
static uint8_t sBuf[256];   // CDC staging: replies go to the host per line, never per byte
static size_t sLen = 0;
static void sFlush() {
  // Only a CDC host that asserted DTR/RTS sees serial output. Bulk write + setTxTimeoutMs(10):
  // a reading host never waits, a host gone with stale DTR costs at most ~200 ms per line instead
  // of stalling loop() per byte (a BLE param push froze the board at ~1 fps that way), and a brief
  // read hiccup rides through instead of dropping bytes mid-line.
  if (sLen && Serial.isConnected()) Serial.write(sBuf, sLen);
  sLen = 0;
}
size_t DualOut::write(uint8_t c) {
  sBuf[sLen++] = c; if (c == '\n' || sLen >= sizeof(sBuf)) sFlush();
  if (connected) { txBuf[txLen++] = c; if (c == '\n' || txLen >= txMax()) txFlush(); }
  return 1;
}
size_t DualOut::write(const uint8_t *buf, size_t n) { for (size_t i = 0; i < n; i++) write(buf[i]); return n; }
#endif  // NO_BLE
