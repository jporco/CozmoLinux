# Variáveis de ambiente do Cozmo Companion

Arquivo gerado por `scripts/generate-env-map.py`.

| Variável | Default(s) no código | Local(is) |
|---|---|---|
| `AWAKE_APOS_DESPERTAR_S` | `'900'` | `src/cozmo_companion/core/vida.py:37` |
| `AWAKE_MAX_S` | `'2400'` | `src/cozmo_companion/core/vida.py:36` |
| `AWAKE_MIN_S` | `'1800'` | `src/cozmo_companion/core/vida.py:35` |
| `BAGE_CIDADE` | `'Bagé'`, `'Bagé-RS'` | `src/cozmo_companion/core/hora.py:11`<br>`src/cozmo_companion/weather/bage.py:29` |
| `BAGE_LAT` | `BAGE_LAT` | `src/cozmo_companion/weather/bage.py:27` |
| `BAGE_LON` | `BAGE_LON` | `src/cozmo_companion/weather/bage.py:28` |
| `BAGE_TZ` | `'America/Sao_Paulo'`, `FUSO` | `src/cozmo_companion/core/hora.py:10`<br>`src/cozmo_companion/weather/bage.py:30` |
| `BARULHO_COOLDOWN_S` | `'6'` | `src/cozmo_companion/core/companion_voz.py:635` |
| `BASE_ANIM_CHANCE` | `'0.32'`, `'0.85'` | `src/cozmo_companion/core/companion_legacy.py:2319`<br>`src/cozmo_companion/core/vida.py:374` |
| `BASE_ANIM_MAX_S` | `'55'` | `src/cozmo_companion/core/vida.py:91` |
| `BASE_ANIM_MIN_S` | `'14'`, `'20'` | `src/cozmo_companion/core/limites.py:38`<br>`src/cozmo_companion/core/vida.py:90` |
| `BASE_BOOT_TICKS` | `'8'` | `src/cozmo_companion/core/charger.py:207` |
| `BASE_BOTAO_LOCK_S` | `'8'` | `src/cozmo_companion/core/charger.py:541`<br>`src/cozmo_companion/core/charger.py:523`<br>`src/cozmo_companion/core/charger.py:511` |
| `BASE_CAM_OFF_MAX_S` | `'70'` | `src/cozmo_companion/core/vida.py:110` |
| `BASE_CAM_OFF_MIN_S` | `'35'` | `src/cozmo_companion/core/vida.py:109` |
| `BASE_CAM_ON_MAX_S` | `'12'`, `'22'` | `src/cozmo_companion/core/vida.py:112`<br>`src/cozmo_companion/core/vida.py:175` |
| `BASE_CAM_ON_S` | `'10'`, `'14'` | `src/cozmo_companion/core/vida.py:111`<br>`src/cozmo_companion/core/vida.py:252` |
| `BASE_HEAD_FRAC` | `'0.62'` | `src/cozmo_companion/core/motor_cozmo.py:3733` |
| `BASE_HEAD_MOVE_S` | `'22'` | `src/cozmo_companion/core/alive.py:73` |
| `BASE_HEAD_RESET` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:3750` |
| `BASE_HEAD_SPEED` | `'6.0'`, `'8.0'` | `src/cozmo_companion/core/alive.py:84`<br>`src/cozmo_companion/core/motor_cozmo.py:3757` |
| `BASE_HEAD_TOL_RAD` | `'0.09'` | `src/cozmo_companion/core/motor_cozmo.py:3740` |
| `BASE_MODO_BOTAO` | `'1'`, `None` | `src/cozmo_companion/__test__/test_charger.py:81`<br>`src/cozmo_companion/__test__/test_charger.py:198`<br>`src/cozmo_companion/__test__/test_charger.py:239`<br>`src/cozmo_companion/__test__/test_charger.py:262`<br>`src/cozmo_companion/__test__/test_charger.py:287`<br>`src/cozmo_companion/__test__/test_charger.py:311`<br>`src/cozmo_companion/__test__/test_charger.py:331`<br>`src/cozmo_companion/__test__/test_charger.py:354`<br>`src/cozmo_companion/__test__/test_charger.py:379`<br>`src/cozmo_companion/__test__/test_charger.py:400`<br>`src/cozmo_companion/__test__/test_mesa.py:101`<br>`src/cozmo_companion/__test__/test_motors.py:35`<br>`src/cozmo_companion/__test__/test_toggle_botao.py:42`<br>`src/cozmo_companion/core/charger.py:63` |
| `BASE_NUNCA_SAIR` | `'1'`, `None` | `src/cozmo_companion/__test__/test_charger.py:79`<br>`src/cozmo_companion/__test__/test_charger.py:109`<br>`src/cozmo_companion/__test__/test_charger.py:426`<br>`src/cozmo_companion/core/charger.py:657`<br>`src/cozmo_companion/core/charger.py:422`<br>`src/cozmo_companion/core/companion_legacy.py:672`<br>`src/cozmo_companion/core/companion_legacy.py:933` |
| `BASE_PICKUP_OFF_S` | `'1.2'` | `src/cozmo_companion/core/charger.py:570` |
| `BASE_PICKUP_S` | `'0.5'` | `src/cozmo_companion/core/charger.py:618` |
| `BASE_TICKS_SAIR` | `'200'` | `src/cozmo_companion/core/charger.py:248` |
| `BASE_TOGGLE_DEBOUNCE_S` | `'3'`, `'3.0'` | `src/cozmo_companion/core/charger.py:495`<br>`src/cozmo_companion/core/companion.py:636`<br>`src/cozmo_companion/core/companion_legacy.py:1966` |
| `BASE_VIVO_ANIM_MIN_S` | `'14'` | `src/cozmo_companion/core/companion_legacy.py:2316`<br>`src/cozmo_companion/core/companion_legacy.py:2361` |
| `BASE_VIVO_S` | `'22'`, `'38'` | `src/cozmo_companion/core/companion_legacy.py:2297`<br>`src/cozmo_companion/core/companion_legacy.py:3171` |
| `BASE_VOICE_REACTIONS_ONLY` | `'1'` | `src/cozmo_companion/core/companion_voz.py:695` |
| `BASE_VOICE_REACTION_COOLDOWN_S` | `'4'` | `src/cozmo_companion/core/companion_voz.py:699` |
| `BASE_VOL_BOOT` | `'3.85'` | `src/cozmo_companion/core/charger.py:204`<br>`src/cozmo_companion/core/charger.py:568`<br>`src/cozmo_companion/core/charger.py:586`<br>`src/cozmo_companion/core/companion_legacy.py:858` |
| `BASE_VOL_MIN_SAIR` | `'3.55'` | `src/cozmo_companion/core/charger.py:659`<br>`src/cozmo_companion/core/companion_legacy.py:857` |
| `BASE_VOZ_SOMENTE_WAKE` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:1480`<br>`src/cozmo_companion/core/companion_voz.py:741` |
| `BATTERY_ANNOUNCE` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2492` |
| `BATTERY_CHARGE_RESUME_PCT` | `'60'` | `src/cozmo_companion/core/charger.py:54` |
| `BATTERY_CHARGE_STOP_PCT` | `'90'` | `src/cozmo_companion/core/charger.py:53`<br>`src/cozmo_companion/core/charger.py:170`<br>`src/cozmo_companion/core/motor_cozmo.py:1038`<br>`src/cozmo_companion/core/motor_cozmo.py:1325` |
| `BATTERY_DROP_SPIKE_V` | `'0.25'` | `src/cozmo_companion/core/charger.py:56` |
| `BATTERY_MIN_PCT` | `'60'` | `src/cozmo_companion/core/charger.py:52` |
| `BATTERY_TTS_MIN_V` | `'3.85'` | `src/cozmo_companion/core/companion_legacy.py:1032` |
| `BOTAO_FILA_DRAIN_S` | `'10'` | `src/cozmo_companion/core/companion.py:620`<br>`src/cozmo_companion/core/companion_legacy.py:1924` |
| `BOTAO_OLED_S` | `'2.5'` | `src/cozmo_companion/core/companion.py:580`<br>`src/cozmo_companion/core/companion_legacy.py:1890` |
| `BOTAO_QUIET_S` | `'4'`, `'5'` | `src/cozmo_companion/core/companion.py:581`<br>`src/cozmo_companion/core/companion_legacy.py:1889`<br>`src/cozmo_companion/core/companion_legacy.py:1886` |
| `BOTAO_TRANSICAO_S` | `'8'`, `os.environ.get('BOTAO_QUIET_S', '5')` | `src/cozmo_companion/core/companion.py:587`<br>`src/cozmo_companion/core/companion_legacy.py:1884` |
| `CAM_OFF_MAX_S` | `'600'` | `src/cozmo_companion/core/vida.py:106` |
| `CAM_OFF_MIN_S` | `'300'` | `src/cozmo_companion/core/vida.py:105` |
| `CAM_ON_MAX_S` | `'20'` | `src/cozmo_companion/core/vida.py:108` |
| `CAM_ON_S` | `'12'` | `src/cozmo_companion/core/vida.py:107` |
| `CARINHO_BASE_ACC_MULT` | `'2.8'` | `src/cozmo_companion/core/head_touch.py:26` |
| `CARINHO_BASE_AND` | `'1'` | `src/cozmo_companion/core/head_touch.py:30` |
| `CARINHO_BASE_ANG_MULT` | `'3.5'` | `src/cozmo_companion/core/head_touch.py:22` |
| `CARINHO_BURST_GAP_S` | `'20'` | `src/cozmo_companion/core/companion.py:560`<br>`src/cozmo_companion/core/companion_legacy.py:1102` |
| `CARINHO_COOLDOWN_S` | `'10'`, `'16'`, `'16' if self._na_base_efetivo() else '8'` | `src/cozmo_companion/core/companion.py:557`<br>`src/cozmo_companion/core/companion_legacy.py:1097`<br>`src/cozmo_companion/core/head_touch.py:13` |
| `CARINHO_LIM_ACC` | `'0.35'` | `src/cozmo_companion/core/head_touch.py:16` |
| `CARINHO_LIM_ACC_SONO` | `'0.22'` | `src/cozmo_companion/core/head_touch.py:18` |
| `CARINHO_LIM_ANG` | `'0.06'` | `src/cozmo_companion/core/head_touch.py:15` |
| `CARINHO_LIM_ANG_SONO` | `'0.035'` | `src/cozmo_companion/core/head_touch.py:17` |
| `CARINHO_LINK_GRACE_S` | `'20'`, `'45'` | `src/cozmo_companion/core/companion.py:298`<br>`src/cozmo_companion/core/companion_legacy.py:428` |
| `CARINHO_OLED_HOLD_S` | `'1.2'` | `src/cozmo_companion/core/fila_cozmo.py:286` |
| `CARINHO_OLED_S` | `'3.5'` | `src/cozmo_companion/core/fila_cozmo.py:284` |
| `CARINHO_UDP_QUIET_S` | `'10'` | `src/cozmo_companion/core/companion_legacy.py:1124` |
| `CHAT_ENABLED` | `'1'` | `src/cozmo_companion/core/companion.py:101`<br>`src/cozmo_companion/core/companion_legacy.py:179` |
| `CLIFF_MIN_RAW` | `'380'` | `src/cozmo_companion/core/mesa.py:32` |
| `CLIFF_RATIO` | `'0.58'` | `src/cozmo_companion/core/mesa.py:33` |
| `COOLDOWN_VOZ_BASE_S` | `'12'`, `'3'` | `src/cozmo_companion/core/companion_legacy.py:1251`<br>`src/cozmo_companion/core/companion_legacy.py:1874`<br>`src/cozmo_companion/core/companion_voz.py:531` |
| `COZMO01_AUTO_COOLDOWN_S` | `'18'` | `src/cozmo_companion/core/motor_cozmo.py:4211` |
| `COZMO01_CLIP_ACK_S` | `'0.45'` | `src/cozmo_companion/core/motor_cozmo.py:4171` |
| `COZMO01_DISCONNECT_PAUSE_S` | `os.environ.get('COZMO_DISCONNECT_PAUSE_S', '5')` | `src/cozmo_companion/core/companion.py:1096` |
| `COZMO01_DRAIN_S` | `'4'` | `src/cozmo_companion/core/motor_cozmo.py:4072` |
| `COZMO01_EMERG_COOLDOWN_S` | `'3'` | `src/cozmo_companion/core/cozmo01_recovery.py:81` |
| `COZMO01_EMERG_MIN_S` | `'4'` | `src/cozmo_companion/core/cozmo01_recovery.py:127` |
| `COZMO01_KEEPER_RX_DEAD_MAX_S` | `'180'` | `src/cozmo_companion/core/cozmo01_recovery.py:142` |
| `COZMO01_LOG_DEBOUNCE_S` | `'300'` | `src/cozmo_companion/core/companion_legacy.py:2611` |
| `COZMO01_OLED_RECENT_S` | `'45'` | `src/cozmo_companion/core/motor_cozmo.py:804` |
| `COZMO01_OLED_TIMEOUT_S` | `'18'` | `src/cozmo_companion/core/motor_cozmo.py:4107` |
| `COZMO01_PING_GAP_S` | `'0.12'` | `src/cozmo_companion/core/motor_cozmo.py:4118` |
| `COZMO01_PREVENT_DTX` | `'150'` | `src/cozmo_companion/core/cozmo01_recovery.py:47` |
| `COZMO01_RESET_COOLDOWN_S` | `'10'` | `src/cozmo_companion/core/cozmo01_recovery.py:82` |
| `COZMO01_RESET_FAILS` | `'3'` | `src/cozmo_companion/core/cozmo01_recovery.py:116` |
| `COZMO01_RESET_STALL_TICKS` | `'2'` | `src/cozmo_companion/core/cozmo01_recovery.py:117` |
| `COZMO01_RX_DEAD_MAX_S` | `'12'` | `src/cozmo_companion/core/cozmo01_recovery.py:157` |
| `COZMO01_RX_DEAD_S` | `'8'` | `src/cozmo_companion/core/conexao.py:655`<br>`src/cozmo_companion/core/motor_cozmo.py:4088` |
| `COZMO01_SLEEP_TIMEOUT_S` | `'50'` | `src/cozmo_companion/core/motor_cozmo.py:4112` |
| `COZMO01_STALL_MAX_S` | `'10'` | `src/cozmo_companion/core/cozmo01_recovery.py:126` |
| `COZMO01_WATCHDOG_COOLDOWN_S` | `'20'` | `src/cozmo_companion/core/companion.py:1238` |
| `COZMO01_WATCHDOG_S` | `'30'` | `src/cozmo_companion/core/companion.py:1237` |
| `COZMO_ALLOW_MULTI` | `'0'` | `src/cozmo_companion/core/singleton.py:18` |
| `COZMO_ANIM_BASE_HOLD_S` | `'2.5'`, `'4'` | `src/cozmo_companion/core/companion.py:506`<br>`src/cozmo_companion/core/companion_legacy.py:796`<br>`src/cozmo_companion/core/companion_legacy.py:3060`<br>`src/cozmo_companion/core/companion_legacy.py:3046`<br>`src/cozmo_companion/core/motor_cozmo.py:509` |
| `COZMO_ANIM_CARGA_S` | `'180'` | `src/cozmo_companion/core/charger.py:795` |
| `COZMO_ANIM_SOURCE_FPS` | `'30'` | `src/cozmo_companion/core/motor_cozmo.py:1589` |
| `COZMO_ANIM_TRAVADA_S` | `'6'` | `src/cozmo_companion/core/motor_cozmo.py:776` |
| `COZMO_BASE_CLIP_DRAIN_S` | `'4'` | `src/cozmo_companion/core/motor_cozmo.py:1655` |
| `COZMO_BASE_CLIP_LOOP_S` | `'18'` | `src/cozmo_companion/core/motor_cozmo.py:1713` |
| `COZMO_BASE_CLIP_MAX_S` | `'12'`, `'16'` | `src/cozmo_companion/core/motor_cozmo.py:4109`<br>`src/cozmo_companion/core/motor_cozmo.py:1425` |
| `COZMO_BASE_CLIP_REPLAY_MIN_S` | `'14'` | `src/cozmo_companion/core/motor_cozmo.py:2329` |
| `COZMO_BASE_DESPERTAR_S` | `'35'` | `src/cozmo_companion/core/companion.py:1338` |
| `COZMO_BASE_FACE_HZ` | `'0.25'` | `src/cozmo_companion/core/motor_cozmo.py:3885` |
| `COZMO_BASE_FULL_KEEPER_HZ` | `'4'`, `'7'` | `src/cozmo_companion/core/motor_cozmo.py:1576`<br>`src/cozmo_companion/core/motor_cozmo.py:3199` |
| `COZMO_BASE_HEAD_MAX_DEG` | `'6'` | `src/cozmo_companion/core/anim_base_patch.py:45` |
| `COZMO_BASE_IDLE_PESO` | `'0.35'` | `src/cozmo_companion/core/motor_cozmo.py:1081` |
| `COZMO_BASE_KEEPER_VIVO` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:3083`<br>`src/cozmo_companion/core/motor_cozmo.py:4696`<br>`src/cozmo_companion/core/motor_cozmo.py:1265`<br>`src/cozmo_companion/core/motor_cozmo.py:3169`<br>`src/cozmo_companion/core/motor_cozmo.py:3844`<br>`src/cozmo_companion/core/motor_cozmo.py:4467`<br>`src/cozmo_companion/core/motor_cozmo.py:3568` |
| `COZMO_BASE_OLED_ANIMATED` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:1478` |
| `COZMO_BASE_OLED_ANIM_LOOP` | `'auto'` | `src/cozmo_companion/core/motor_cozmo.py:1441` |
| `COZMO_BASE_OLED_CHARGER` | `'1'` | `src/cozmo_companion/core/conexao.py:942`<br>`src/cozmo_companion/core/fila_cozmo.py:348`<br>`src/cozmo_companion/core/motor_cozmo.py:1333`<br>`src/cozmo_companion/core/motor_cozmo.py:2146` |
| `COZMO_BASE_OLED_CHARGER_FULL` | `'0'` | `src/cozmo_companion/core/conexao.py:943`<br>`src/cozmo_companion/core/motor_cozmo.py:1317` |
| `COZMO_BASE_OLED_HOLD_MAX_S` | `'12'`, `'15'` | `src/cozmo_companion/core/fila_cozmo.py:118`<br>`src/cozmo_companion/core/motor_cozmo.py:443`<br>`src/cozmo_companion/notifications/core/handler.py:169` |
| `COZMO_BASE_OLED_HOLD_STACK` | `'2.5'` | `src/cozmo_companion/core/motor_cozmo.py:448` |
| `COZMO_BASE_OLED_KEEPALIVE` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:2489`<br>`src/cozmo_companion/core/motor_cozmo.py:1447` |
| `COZMO_BASE_OLED_KEEPALIVE_HZ` | `'5'` | `src/cozmo_companion/core/motor_cozmo.py:2426` |
| `COZMO_BASE_OLED_LOOP_BACKOFF_S` | `'240'` | `src/cozmo_companion/core/motor_cozmo.py:1489` |
| `COZMO_BASE_OLED_MIN` | `'1'` | `src/cozmo_companion/core/conexao.py:945`<br>`src/cozmo_companion/core/motor_cozmo.py:3699`<br>`src/cozmo_companion/core/motor_cozmo.py:3641` |
| `COZMO_BASE_OLED_MIN_FRAMES` | `'8'` | `src/cozmo_companion/core/anim_base_patch.py:155`<br>`src/cozmo_companion/core/motor_cozmo.py:1110`<br>`src/cozmo_companion/core/motor_cozmo.py:2224`<br>`src/cozmo_companion/core/motor_cozmo.py:2321` |
| `COZMO_BASE_OLED_MODE` | `'proc'` | `src/cozmo_companion/core/motor_cozmo.py:1449`<br>`src/cozmo_companion/core/motor_cozmo.py:3684` |
| `COZMO_BASE_OLED_TX_RX_STALL_GRACE_S` | `'180'` | `src/cozmo_companion/core/motor_cozmo.py:831` |
| `COZMO_BASE_POOL_SEGURO` | `'1'` | `src/cozmo_companion/core/anims.py:577` |
| `COZMO_BASE_PROC_HZ` | `'2'`, `'3'` | `src/cozmo_companion/core/motor_cozmo.py:3285`<br>`src/cozmo_companion/core/motor_cozmo.py:3548` |
| `COZMO_BASE_PULSE_PROC` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:3720` |
| `COZMO_BASE_SEMPRE_CARGA` | `'0'`, `None` | `src/cozmo_companion/__test__/test_charger.py:219`<br>`src/cozmo_companion/core/charger.py:141` |
| `COZMO_BASE_STALL_PULSO_S` | `'1.5'` | `src/cozmo_companion/core/cozmo01_recovery.py:132` |
| `COZMO_BASE_STOP_RODAS_CMD` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:884` |
| `COZMO_BASE_TX_BACKPRESSURE_S` | `'1.5'` | `src/cozmo_companion/core/motor_cozmo.py:819` |
| `COZMO_BASE_TX_STALL` | `'280'` | `src/cozmo_companion/core/config.py:25` |
| `COZMO_BASE_VARIAR_ANTI_REPEAT` | `'3'` | `src/cozmo_companion/core/motor_cozmo.py:1074`<br>`src/cozmo_companion/core/motor_cozmo.py:1238`<br>`src/cozmo_companion/core/motor_cozmo.py:1544` |
| `COZMO_BASE_VARIAR_CHANCE` | `'0.38'` | `src/cozmo_companion/core/motor_cozmo.py:1217` |
| `COZMO_BASE_VARIAR_EXTRA_MAX` | `'14'` | `src/cozmo_companion/core/anims.py:547` |
| `COZMO_BASE_VARIAR_FORCADO_MIN_S` | `'8'` | `src/cozmo_companion/core/motor_cozmo.py:1213` |
| `COZMO_BASE_VARIAR_JITTER_S` | `'8'` | `src/cozmo_companion/core/motor_cozmo.py:1624` |
| `COZMO_BASE_VARIAR_LUZ` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:1169` |
| `COZMO_BASE_VARIAR_MAX_S` | `'55'` | `src/cozmo_companion/core/motor_cozmo.py:1625` |
| `COZMO_BASE_VARIAR_S` | `'32'`, `'38'` | `src/cozmo_companion/core/motor_cozmo.py:1623`<br>`src/cozmo_companion/core/motor_cozmo.py:1208` |
| `COZMO_BASE_WAKE_ANIM` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:4032` |
| `COZMO_BOOT_ACORDADO` | `'1'` | `src/cozmo_companion/core/companion.py:1682`<br>`src/cozmo_companion/core/companion.py:1712` |
| `COZMO_BOOT_FRESH_SESSION` | `'0'` | `src/cozmo_companion/core/companion.py:1175` |
| `COZMO_BOOT_OI` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:3173` |
| `COZMO_BOOT_QUIET_S` | `'4'`, `os.environ.get('COZMO_POST_RECONNECT_S', '10')` | `src/cozmo_companion/core/companion.py:1771`<br>`src/cozmo_companion/core/companion_legacy.py:3162` |
| `COZMO_BOOT_RX_FRESH_MAX` | `'220'` | `src/cozmo_companion/core/conexao.py:799` |
| `COZMO_BOOT_RX_MIN` | `'20'` | `src/cozmo_companion/core/conexao.py:807` |
| `COZMO_CHARGER_AWAKE_IDLE` | `'IdleOnCharger'`, `None` | `src/cozmo_companion/core/motor_cozmo.py:1031`<br>`src/cozmo_companion/core/motor_cozmo.py:2973`<br>`src/cozmo_companion/core/motor_cozmo.py:1191`<br>`src/cozmo_companion/core/motor_cozmo.py:1170`<br>`src/cozmo_companion/core/motor_cozmo.py:1542`<br>`src/cozmo_companion/core/motor_cozmo.py:3183`<br>`src/cozmo_companion/core/motor_cozmo.py:4238` |
| `COZMO_CHARGER_CLIP_S` | `'14'` | `src/cozmo_companion/core/motor_cozmo.py:1418` |
| `COZMO_CHARGER_LOOP_PAUSE_S` | `'0.12'` | `src/cozmo_companion/core/motor_cozmo.py:1917` |
| `COZMO_CHARGER_OLED_HZ` | `'1.5'`, `'2.5'`, `'4'` | `src/cozmo_companion/core/motor_cozmo.py:2821`<br>`src/cozmo_companion/core/motor_cozmo.py:1578`<br>`src/cozmo_companion/core/motor_cozmo.py:3265` |
| `COZMO_CHARGER_OLED_KEEPER` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:2090` |
| `COZMO_CHARGER_PLAY_STREAM` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:1446`<br>`src/cozmo_companion/core/motor_cozmo.py:2121`<br>`src/cozmo_companion/core/motor_cozmo.py:2135` |
| `COZMO_CHARGER_REPLAY_S` | `'18'` | `src/cozmo_companion/core/motor_cozmo.py:2823` |
| `COZMO_CHARGER_STREAM_NA_CHEIA` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:2123` |
| `COZMO_CHARGE_IDLE_S` | `'18'` | `src/cozmo_companion/core/charger.py:777`<br>`src/cozmo_companion/core/motor_cozmo.py:4584` |
| `COZMO_COMPANION_ROOT` | `''`, `'/mnt/G/PROJETOS/cozmo-companion'` | `src/cozmo_companion/core/conexao.py:15`<br>`src/cozmo_companion/core/paths.py:10`<br>`src/cozmo_companion/guardian/__main__.py:44` |
| `COZMO_CONNECT_PAUSE_S` | `'5'` | `src/cozmo_companion/core/conexao.py:936` |
| `COZMO_CONNECT_TIMEOUT` | `'30'` | `src/cozmo_companion/core/conexao.py:934` |
| `COZMO_CONNECT_TRIES` | `'5'` | `src/cozmo_companion/core/conexao.py:935` |
| `COZMO_COZMO01_RESET_UDP` | `'1'` | `src/cozmo_companion/core/conexao.py:155` |
| `COZMO_DEBUG_TRACE` | `'0'` | `src/cozmo_companion/core/debug_trace.py:25` |
| `COZMO_DEBUG_TRACE_LOG` | `'/mnt/G/PROJETOS/cozmo-companion/.cursor/debug-trace.log'` | `src/cozmo_companion/core/debug_trace.py:10` |
| `COZMO_DIAG_S` | `'90'` | `src/cozmo_companion/core/companion_legacy.py:2915` |
| `COZMO_DISCONNECT_PAUSE_MIN_S` | `'0.3'` | `src/cozmo_companion/core/conexao.py:1019` |
| `COZMO_DISCONNECT_PAUSE_S` | `'12'`, `'5'` | `src/cozmo_companion/core/companion.py:1101`<br>`src/cozmo_companion/core/companion.py:1098`<br>`src/cozmo_companion/core/companion_legacy.py:2634`<br>`src/cozmo_companion/core/conexao.py:1013` |
| `COZMO_ESCURO_AMOSTRAS` | `'4'` | `src/cozmo_companion/core/ambiente_escuro.py:21` |
| `COZMO_ESCURO_AUTO` | `'1'` | `src/cozmo_companion/core/ambiente_escuro.py:18`<br>`src/cozmo_companion/core/face_watch.py:131`<br>`src/cozmo_companion/core/face_watch.py:163` |
| `COZMO_ESCURO_CLARO` | `'50'` | `src/cozmo_companion/core/ambiente_escuro.py:20` |
| `COZMO_ESCURO_DESPERTAR_S` | `'180'` | `src/cozmo_companion/core/ambiente_escuro.py:25`<br>`src/cozmo_companion/notifications/core/handler.py:123` |
| `COZMO_ESCURO_ESPIAR_CHANCE` | `'0.38'` | `src/cozmo_companion/core/motor_cozmo.py:1298` |
| `COZMO_ESCURO_ESPIAR_INTERVALO_S` | `'360'` | `src/cozmo_companion/core/motor_cozmo.py:1295` |
| `COZMO_ESCURO_ESPIAR_S` | `'14'` | `src/cozmo_companion/core/motor_cozmo.py:1305` |
| `COZMO_ESCURO_LIM` | `'32'` | `src/cozmo_companion/core/ambiente_escuro.py:19` |
| `COZMO_ESCURO_NA_BASE` | `'0'` | `src/cozmo_companion/core/ambiente_escuro.py:168` |
| `COZMO_ESCURO_PROBE_DELAY_S` | `'300'` | `src/cozmo_companion/core/ambiente_escuro.py:24` |
| `COZMO_ESCURO_PROBE_INTERVALO_S` | `'90'` | `src/cozmo_companion/core/ambiente_escuro.py:23` |
| `COZMO_ESCURO_PROBE_S` | `'5'` | `src/cozmo_companion/core/ambiente_escuro.py:22` |
| `COZMO_ESCURO_VARIAR_S` | `'75'` | `src/cozmo_companion/core/motor_cozmo.py:1206` |
| `COZMO_FACE_BASE` | `'0'`, `'1'` | `src/cozmo_companion/core/companion.py:1515`<br>`src/cozmo_companion/core/companion_legacy.py:509`<br>`src/cozmo_companion/core/companion_legacy.py:3206`<br>`src/cozmo_companion/core/face_watch.py:76`<br>`src/cozmo_companion/core/face_watch.py:123`<br>`src/cozmo_companion/core/face_watch.py:130`<br>`src/cozmo_companion/core/face_watch.py:191`<br>`src/cozmo_companion/core/vida.py:172`<br>`src/cozmo_companion/core/vida.py:758` |
| `COZMO_FACE_BASE_FORCE` | `'0'` | `src/cozmo_companion/core/face_watch.py:124`<br>`src/cozmo_companion/core/face_watch.py:164` |
| `COZMO_FACE_KEEP_S` | `'8'` | `src/cozmo_companion/core/companion.py:906` |
| `COZMO_FACE_PING_MESA_S` | `'12'` | `src/cozmo_companion/core/companion_legacy.py:2966` |
| `COZMO_FACE_PING_S` | `'15'` | `src/cozmo_companion/core/companion_legacy.py:2993` |
| `COZMO_FACE_REFRESH_BASE_S` | `'22'` | `src/cozmo_companion/core/companion_legacy.py:3035` |
| `COZMO_FILA_ANIM_HOLD_S` | `'0.25'` | `src/cozmo_companion/core/fila_cozmo.py:489` |
| `COZMO_FILA_ATIVA` | `'1'` | `src/cozmo_companion/core/fila_cozmo.py:214`<br>`src/cozmo_companion/core/fila_cozmo.py:671` |
| `COZMO_FILA_ESTADO_MAX_S` | `'15'` | `src/cozmo_companion/core/fila_cozmo.py:674` |
| `COZMO_FILA_QUIET_S` | `'0.8'` | `src/cozmo_companion/core/fila_cozmo.py:156`<br>`src/cozmo_companion/notifications/core/handler.py:161` |
| `COZMO_FILA_TIMEOUT_S` | `'6'` | `src/cozmo_companion/core/fila_cozmo.py:153` |
| `COZMO_FULL_CHARGE_WAKE` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:3590` |
| `COZMO_FULL_CHARGE_WAKE_S` | `'12'` | `src/cozmo_companion/core/motor_cozmo.py:3596` |
| `COZMO_INPLACE_FAIL_MAX` | `'2'`, `'3'` | `src/cozmo_companion/core/companion.py:1031`<br>`src/cozmo_companion/core/companion_legacy.py:2607`<br>`src/cozmo_companion/core/companion_legacy.py:2712`<br>`src/cozmo_companion/core/companion_legacy.py:1843` |
| `COZMO_INPLACE_PAUSE_S` | `'1.5'` | `src/cozmo_companion/core/conexao.py:844` |
| `COZMO_INPLACE_QUIET_S` | `'20'` | `src/cozmo_companion/core/companion_legacy.py:2898` |
| `COZMO_IP` | `'172.31.1.1'` | `src/cozmo_companion/core/conexao.py:16`<br>`src/cozmo_companion/core/radio_keepalive.py:52` |
| `COZMO_KEEPALIVE_S` | `'10'`, `'8'` | `src/cozmo_companion/core/companion.py:1206`<br>`src/cozmo_companion/core/companion_legacy.py:2763` |
| `COZMO_KEEPER_DURING_TTS` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:3316` |
| `COZMO_LOCK_FILE` | `'/tmp/cozmo-companion.lock'` | `src/cozmo_companion/core/singleton.py:21` |
| `COZMO_MANTER_ROSTO_S` | `'2.5'` | `src/cozmo_companion/core/companion_legacy.py:3061` |
| `COZMO_MAX_OLED_CHARS` | `'16'` | `src/cozmo_companion/core/fila_cozmo.py:147`<br>`src/cozmo_companion/notifications/core/policy.py:139` |
| `COZMO_MAX_TTS_SINAL_WORDS` | `'1'` | `src/cozmo_companion/core/fila_cozmo.py:150` |
| `COZMO_MOTOR_STOP_BASE_S` | `'0.45'` | `src/cozmo_companion/core/charger.py:833` |
| `COZMO_MOTOR_STOP_CHARGE_S` | `'3.0'` | `src/cozmo_companion/core/charger.py:837` |
| `COZMO_MOTOR_STOP_S` | `'0.45'` | `src/cozmo_companion/core/charger.py:829` |
| `COZMO_NEVER_DISCONNECT` | `'1'` | `src/cozmo_companion/core/companion.py:1903`<br>`src/cozmo_companion/core/companion_legacy.py:3272`<br>`src/cozmo_companion/core/conexao.py:126`<br>`src/cozmo_companion/core/conexao.py:538` |
| `COZMO_NICE` | `'10'` | `src/cozmo_companion/core/companion.py:1897`<br>`src/cozmo_companion/core/companion_legacy.py:3268` |
| `COZMO_NOTIF_ANIM_FIRST` | `'1'` | `src/cozmo_companion/core/fila_cozmo.py:342` |
| `COZMO_NOTIF_ANIM_NA_BASE` | `'0'` | `src/cozmo_companion/core/fila_cozmo.py:343` |
| `COZMO_OFFLINE_BACKOFF_MAX_S` | `'600'` | `src/cozmo_companion/core/companion.py:1907` |
| `COZMO_OFFLINE_BACKOFF_S` | `'120'` | `src/cozmo_companion/core/companion.py:1906` |
| `COZMO_OFFLINE_LOG_S` | `'300'` | `src/cozmo_companion/core/conexao.py:234` |
| `COZMO_OFFLINE_QUIET_S` | `'45'` | `src/cozmo_companion/core/companion.py:1273` |
| `COZMO_OLED_DIRECT` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:4461` |
| `COZMO_OLED_FONT_SIZE` | `'10'` | `src/cozmo_companion/display/face.py:24` |
| `COZMO_OLED_HZ_AMARELO` | `'3'` | `src/cozmo_companion/core/motor_cozmo.py:90` |
| `COZMO_OLED_HZ_LARANJA` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:91` |
| `COZMO_OLED_HZ_VERDE` | `str(base_hz)` | `src/cozmo_companion/core/motor_cozmo.py:89` |
| `COZMO_OLED_HZ_VERMELHO` | `'0.2'` | `src/cozmo_companion/core/motor_cozmo.py:92` |
| `COZMO_OLED_KEEPALIVE_S` | `'0.45'` | `src/cozmo_companion/core/motor_cozmo.py:3896` |
| `COZMO_OLED_MAX_ESTATICO_S` | `'18'` | `src/cozmo_companion/core/motor_cozmo.py:585` |
| `COZMO_OLED_NA_BASE` | `'0'` | `src/cozmo_companion/core/companion.py:411`<br>`src/cozmo_companion/core/fila_cozmo.py:347`<br>`src/cozmo_companion/core/motor_cozmo.py:4452` |
| `COZMO_OLED_PHASE_UPGRADE_S` | `'45'` | `src/cozmo_companion/core/motor_cozmo.py:111` |
| `COZMO_OLED_REFRESH_S` | `'12'`, `'2.5'` | `src/cozmo_companion/core/motor_cozmo.py:3888`<br>`src/cozmo_companion/display/face.py:143` |
| `COZMO_OLED_WATCHDOG_S` | `'4'` | `src/cozmo_companion/core/motor_cozmo.py:679` |
| `COZMO_PING_INTERVAL_S` | `'0.5'` | `src/cozmo_companion/core/motor_cozmo.py:3767` |
| `COZMO_PING_OOB_S` | `'4.5'` | `src/cozmo_companion/core/companion_legacy.py:3100` |
| `COZMO_PING_PRE_CLIP` | `'2'` | `src/cozmo_companion/core/motor_cozmo.py:2282` |
| `COZMO_PING_TIMEOUT_S` | `'4'` | `src/cozmo_companion/core/conexao.py:135` |
| `COZMO_POST_RECONNECT_S` | `'10'`, `'22'`, `'35'`, `'60'` | `src/cozmo_companion/core/companion.py:248`<br>`src/cozmo_companion/core/companion.py:358`<br>`src/cozmo_companion/core/companion.py:370`<br>`src/cozmo_companion/core/companion.py:1083`<br>`src/cozmo_companion/core/companion_legacy.py:443`<br>`src/cozmo_companion/core/companion_legacy.py:453`<br>`src/cozmo_companion/core/companion_legacy.py:2624`<br>`src/cozmo_companion/core/companion_legacy.py:2663`<br>`src/cozmo_companion/core/companion_legacy.py:3164`<br>`src/cozmo_companion/core/companion_legacy.py:1832`<br>`src/cozmo_companion/core/companion_legacy.py:1847`<br>`src/cozmo_companion/core/limites.py:34` |
| `COZMO_POST_TTS_RECONNECT` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2710` |
| `COZMO_POST_TTS_RECONNECT_S` | `'90'` | `src/cozmo_companion/core/companion_legacy.py:2706` |
| `COZMO_POS_TTS_BASE_S` | `'18'` | `src/cozmo_companion/core/companion_legacy.py:416`<br>`src/cozmo_companion/core/companion_legacy.py:1803`<br>`src/cozmo_companion/core/companion_voz.py:137` |
| `COZMO_PPCLIP_RX_STALL_S` | `'120'` | `src/cozmo_companion/core/conexao.py:649` |
| `COZMO_PREVENT_DTX` | `'220'` | `src/cozmo_companion/core/companion_legacy.py:2799` |
| `COZMO_PROC_CHARGE_IDLE` | `'0'` | `src/cozmo_companion/core/charger.py:789` |
| `COZMO_PROC_FACE` | `'1'` | `src/cozmo_companion/core/companion.py:294`<br>`src/cozmo_companion/core/companion_legacy.py:3090`<br>`src/cozmo_companion/core/companion_legacy.py:1869`<br>`src/cozmo_companion/core/companion_legacy.py:1931`<br>`src/cozmo_companion/core/conexao.py:950`<br>`src/cozmo_companion/core/motor_cozmo.py:3989`<br>`src/cozmo_companion/core/motor_cozmo.py:4351`<br>`src/cozmo_companion/core/motor_cozmo.py:4444`<br>`src/cozmo_companion/display/face.py:129` |
| `COZMO_PROC_FACE_BASE` | `'0'`, `'1'` | `src/cozmo_companion/core/charger.py:796`<br>`src/cozmo_companion/core/companion.py:293`<br>`src/cozmo_companion/core/companion_legacy.py:2937`<br>`src/cozmo_companion/core/conexao.py:850`<br>`src/cozmo_companion/core/face_watch.py:385`<br>`src/cozmo_companion/core/motor_cozmo.py:2102`<br>`src/cozmo_companion/core/motor_cozmo.py:3948`<br>`src/cozmo_companion/core/motor_cozmo.py:3833`<br>`src/cozmo_companion/core/motor_cozmo.py:3987`<br>`src/cozmo_companion/core/vida.py:228`<br>`src/cozmo_companion/core/vida.py:559` |
| `COZMO_PROC_RX_STALL_S` | `'120'` | `src/cozmo_companion/core/config.py:27` |
| `COZMO_PROC_STALL_RATIO_MAX` | `'8.0'` | `src/cozmo_companion/core/conexao.py:650` |
| `COZMO_RADIO_KEEPALIVE` | `'1'` | `src/cozmo_companion/core/radio_keepalive.py:27` |
| `COZMO_RADIO_KEEPALIVE_HZ` | `'50'` | `src/cozmo_companion/core/radio_keepalive.py:54` |
| `COZMO_RADIO_KEEPALIVE_PORT` | `'55001'` | `src/cozmo_companion/core/radio_keepalive.py:53` |
| `COZMO_RATIO_PREVENT_COOLDOWN_S` | `'25'`, `'45'` | `src/cozmo_companion/core/companion.py:1073`<br>`src/cozmo_companion/core/companion_legacy.py:2795`<br>`src/cozmo_companion/core/sessao_guard.py:20` |
| `COZMO_RATIO_PREVENT_REC` | `'1.5'` | `src/cozmo_companion/core/companion_legacy.py:2794` |
| `COZMO_READY_S` | `'18'` | `src/cozmo_companion/core/conexao.py:868` |
| `COZMO_RECONNECT_CIRCUIT_S` | `'90'` | `src/cozmo_companion/core/sessao_guard.py:26` |
| `COZMO_RECONNECT_COOLDOWN_S` | `'45'` | `src/cozmo_companion/core/companion_legacy.py:2603` |
| `COZMO_RECONNECT_FORCE_COOLDOWN_S` | `'10'` | `src/cozmo_companion/core/companion_legacy.py:2601` |
| `COZMO_RECONNECT_MAX_FAIL` | `'3'` | `src/cozmo_companion/core/sessao_guard.py:23` |
| `COZMO_RECONNECT_MAX_S` | `'45'` | `src/cozmo_companion/core/conexao.py:1052` |
| `COZMO_RECONNECT_S` | `'12'` | `src/cozmo_companion/core/conexao.py:1051` |
| `COZMO_RECONNECT_WAIT_PING_S` | `'25'` | `src/cozmo_companion/core/companion.py:1085`<br>`src/cozmo_companion/core/companion_legacy.py:2626` |
| `COZMO_RENOVAR_BASE_S` | `'20'` | `src/cozmo_companion/core/motor_cozmo.py:2624`<br>`src/cozmo_companion/core/motor_cozmo.py:2869` |
| `COZMO_RENOVAR_FORCAR_MIN_S` | `'8'` | `src/cozmo_companion/core/motor_cozmo.py:2627` |
| `COZMO_RX_DEAD_RATIO` | `'8.0'` | `src/cozmo_companion/core/conexao.py:823` |
| `COZMO_RX_MAX_ACUM` | `'1500'` | `src/cozmo_companion/core/companion_legacy.py:2797` |
| `COZMO_RX_MIN_VIVO` | `'400'` | `src/cozmo_companion/core/companion_legacy.py:2283` |
| `COZMO_RX_PREVENT_STALL` | `'1500'` | `src/cozmo_companion/core/companion_legacy.py:2798` |
| `COZMO_RX_STALL_PARADO_S` | `'18'` | `src/cozmo_companion/core/config.py:28` |
| `COZMO_RX_STALL_RATIO_S` | `'12'` | `src/cozmo_companion/core/conexao.py:644` |
| `COZMO_RX_STALL_S` | `'12'`, `'30'` | `src/cozmo_companion/core/conexao.py:625`<br>`src/cozmo_companion/core/limites.py:33` |
| `COZMO_RX_STALL_TX_MIN` | `'200'` | `src/cozmo_companion/core/conexao.py:653` |
| `COZMO_SEMPRE_NA_BASE` | `'0'` | `src/cozmo_companion/core/companion.py:273` |
| `COZMO_SENSOR_REACTION_COOLDOWN_S` | `'2.5'` | `src/cozmo_companion/core/companion.py:222` |
| `COZMO_SESSAO_RX_MIN` | `'12'` | `src/cozmo_companion/core/conexao.py:335` |
| `COZMO_SETTLE_S` | `'1.0'` | `src/cozmo_companion/core/conexao.py:974` |
| `COZMO_SHAKE_COOLDOWN_S` | `'5'` | `src/cozmo_companion/core/sensory_reactions.py:61` |
| `COZMO_SHAKE_HITS` | `'3'` | `src/cozmo_companion/core/sensory_reactions.py:60` |
| `COZMO_SHAKE_JERK` | `'0.85'` | `src/cozmo_companion/core/sensory_reactions.py:58` |
| `COZMO_SHAKE_WINDOW_S` | `'1.25'` | `src/cozmo_companion/core/sensory_reactions.py:59` |
| `COZMO_SLEEP_CLIP_HOLD_S` | `'22'`, `'28'` | `src/cozmo_companion/core/motor_cozmo.py:1620`<br>`src/cozmo_companion/core/motor_cozmo.py:1737` |
| `COZMO_SLEEP_CLIP_JITTER_S` | `'10'` | `src/cozmo_companion/core/motor_cozmo.py:1621` |
| `COZMO_SLEEP_DURATION_JITTER_S` | `'120'` | `src/cozmo_companion/core/vida.py:76` |
| `COZMO_SLEEP_DURATION_MIN` | `''` | `src/cozmo_companion/core/vida.py:73` |
| `COZMO_SLEEP_INTERVAL_JITTER_S` | `'90'` | `src/cozmo_companion/core/vida.py:47` |
| `COZMO_SLEEP_INTERVAL_MIN` | `''` | `src/cozmo_companion/core/vida.py:44`<br>`src/cozmo_companion/core/vida.py:55`<br>`src/cozmo_companion/core/vida.py:66` |
| `COZMO_SLEEP_ON_STOP` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:1704` |
| `COZMO_SOMENTE_BASE` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:614` |
| `COZMO_SOM_CARGA` | `'0'` | `src/cozmo_companion/core/charger.py:899`<br>`src/cozmo_companion/core/companion_legacy.py:761` |
| `COZMO_SONO_FLASH_ZZZ` | `'1'` | `src/cozmo_companion/core/motor_cozmo.py:249` |
| `COZMO_SONO_NA_BASE` | `'0'` | `src/cozmo_companion/core/ambiente_escuro.py:166`<br>`src/cozmo_companion/core/companion.py:198`<br>`src/cozmo_companion/core/vida.py:673` |
| `COZMO_SONO_OLED_TEXTO` | `'0'` | `src/cozmo_companion/core/motor_cozmo.py:201` |
| `COZMO_STALL_TICKS` | `'3'` | `src/cozmo_companion/core/companion_legacy.py:2894` |
| `COZMO_STT_IDLE_BASE` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:557`<br>`src/cozmo_companion/core/companion_voz.py:167` |
| `COZMO_STT_NA_BASE` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:548`<br>`src/cozmo_companion/core/companion_voz.py:162` |
| `COZMO_SYNC_BASE_RX_OFF_S` | `'3'` | `src/cozmo_companion/core/motor_cozmo.py:4007` |
| `COZMO_SYNC_BASE_S` | `'5'`, `'8'` | `src/cozmo_companion/core/motor_cozmo.py:2729`<br>`src/cozmo_companion/core/motor_cozmo.py:4005` |
| `COZMO_TELA_MANTEM_PROC_BASE` | `'1'` | `src/cozmo_companion/display/face.py:221`<br>`src/cozmo_companion/display/face.py:258` |
| `COZMO_TTS_POST_QUIET_OK_S` | `'25'` | `src/cozmo_companion/core/companion_legacy.py:1795` |
| `COZMO_TTS_POST_QUIET_S` | `'28'` | `src/cozmo_companion/core/companion_legacy.py:410`<br>`src/cozmo_companion/core/companion_legacy.py:1807`<br>`src/cozmo_companion/core/companion_voz.py:133`<br>`src/cozmo_companion/core/limites.py:36` |
| `COZMO_TTS_PREP_S` | `'0.25'` | `src/cozmo_companion/core/companion_legacy.py:1746` |
| `COZMO_TTS_PRE_QUIET_S` | `'5'` | `src/cozmo_companion/core/limites.py:37` |
| `COZMO_TTS_RECONNECT_BASE` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:1828` |
| `COZMO_TTS_RECONNECT_ON_FAIL` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:1840` |
| `COZMO_TTS_RX_CHECK_S` | `'6'` | `src/cozmo_companion/core/companion_legacy.py:1787`<br>`src/cozmo_companion/core/companion_voz.py:443` |
| `COZMO_TTS_SINAL_QUIET_S` | `'10'`, `'6'`, `'6' if manter_face else '8'`, `'8'` | `src/cozmo_companion/core/companion_legacy.py:345`<br>`src/cozmo_companion/core/companion_legacy.py:1811`<br>`src/cozmo_companion/core/companion_voz.py:306`<br>`src/cozmo_companion/core/companion_voz.py:345`<br>`src/cozmo_companion/core/companion_voz.py:342`<br>`src/cozmo_companion/core/companion_voz.py:448`<br>`src/cozmo_companion/core/fila_cozmo.py:602`<br>`src/cozmo_companion/core/fila_cozmo.py:599` |
| `COZMO_UDP_DELTA_RATIO_LEVE` | `'4.5'` | `src/cozmo_companion/core/conexao.py:464`<br>`src/cozmo_companion/core/governador.py:226` |
| `COZMO_UDP_DELTA_TX_LEVE` | `'450'` | `src/cozmo_companion/core/conexao.py:466` |
| `COZMO_UDP_DELTA_TX_SAT` | `'500'` | `src/cozmo_companion/core/config.py:26` |
| `COZMO_UDP_JANELA_S` | `'30'` | `src/cozmo_companion/core/conexao.py:436` |
| `COZMO_UDP_QUIET_S` | `'12'`, `'20'`, `'25'` | `src/cozmo_companion/core/companion.py:379`<br>`src/cozmo_companion/core/companion_legacy.py:479`<br>`src/cozmo_companion/core/limites.py:35` |
| `COZMO_UDP_RATIO_LEVE` | `'1.35'` | `src/cozmo_companion/core/limites.py:31` |
| `COZMO_UDP_RATIO_MAX` | `'1.75'` | `src/cozmo_companion/core/limites.py:32` |
| `COZMO_VOLUME` | `'62000'` | `src/cozmo_companion/core/som_reacao.py:132`<br>`src/cozmo_companion/notifications/core/som.py:122` |
| `COZMO_VOLUME_FILE` | `'/mnt/G/PROJETOS/cozmo-companion/data/volume.txt'`, `str(data_dir() / 'volume.txt')` | `src/cozmo_companion/core/companion.py:187`<br>`src/cozmo_companion/core/companion_legacy.py:202` |
| `COZMO_VOZ_CMD` | `'/mnt/G/PROJETOS/cozmo-companion/data/voz.cmd'` | `src/cozmo_companion/core/companion_legacy.py:208`<br>`src/cozmo_companion/core/companion_voz.py:118` |
| `COZMO_VOZ_INJECT` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2522`<br>`src/cozmo_companion/core/companion_voz.py:942` |
| `COZMO_WAIT_PING_S` | `'20'` | `src/cozmo_companion/core/companion_legacy.py:3279` |
| `COZMO_WIFI_COOLDOWN_S` | `'60'` | `src/cozmo_companion/core/conexao.py:226`<br>`src/cozmo_companion/core/conexao.py:213` |
| `COZMO_WIFI_IFACE` | `'wlan0'` | `src/cozmo_companion/core/conexao.py:46` |
| `COZMO_WIFI_OFFLINE_RETRY_S` | `'20'` | `src/cozmo_companion/core/config.py:24` |
| `COZMO_WIFI_RESCAN_OFFLINE_S` | `'90'` | `src/cozmo_companion/core/conexao.py:219` |
| `COZMO_WIFI_RESCAN_S` | `'600'` | `src/cozmo_companion/core/conexao.py:169` |
| `COZMO_WIFI_RETRY_S` | `'25'` | `src/cozmo_companion/core/governador.py:95` |
| `COZMO_WIFI_ROUTE_RETRY_S` | `str(network_tuning().wifi_offline_retry_s)` | `src/cozmo_companion/core/conexao.py:203` |
| `COZMO_WIFI_SAFE` | `'1'` | `src/cozmo_companion/core/conexao.py:159` |
| `COZMO_WIFI_STALL_S` | `'25'` | `src/cozmo_companion/core/companion.py:1282` |
| `COZMO_WLAN0_PRESO_GRACA_S` | `'15'` | `src/cozmo_companion/core/conexao.py:104` |
| `DESCANSO_ANIM_MAX_S` | `'90'` | `src/cozmo_companion/core/vida.py:98` |
| `DESCANSO_ANIM_MIN_S` | `'35'` | `src/cozmo_companion/core/vida.py:97` |
| `DORMIR_VOZ_SEM_LLM` | `'1'` | `src/cozmo_companion/core/companion_voz.py:543` |
| `ECO_CHANCE` | `'0'`, `'0.10'` | `src/cozmo_companion/core/companion_legacy.py:2390`<br>`src/cozmo_companion/core/ritmo.py:13` |
| `ESPIRITO_ATIVO` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:617` |
| `ESPIRITO_BASE_MULT` | `'1.5'` | `src/cozmo_companion/core/espirito.py:275`<br>`src/cozmo_companion/core/espirito.py:277` |
| `ESPIRITO_FALA` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2124`<br>`src/cozmo_companion/core/companion_legacy.py:2380`<br>`src/cozmo_companion/core/espirito.py:177` |
| `ESPIRITO_FALA_NA_BASE` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2067` |
| `ESPIRITO_MAX_S` | `'55'` | `src/cozmo_companion/core/espirito.py:27` |
| `ESPIRITO_MESA_MAX_S` | `'14'` | `src/cozmo_companion/core/espirito.py:29` |
| `ESPIRITO_MESA_MIN_S` | `'6'` | `src/cozmo_companion/core/espirito.py:28` |
| `ESPIRITO_MESA_MULT` | `'0.85'` | `src/cozmo_companion/core/espirito.py:280` |
| `ESPIRITO_MIN_S` | `'22'` | `src/cozmo_companion/core/espirito.py:26` |
| `ESPIRITO_NA_BASE` | `'0'`, `'?'` | `src/cozmo_companion/core/companion_legacy.py:3159`<br>`src/cozmo_companion/core/companion_legacy.py:2192` |
| `ESPIRITO_PAUSA_RECONNECT_S` | `'120'`, `'22'` | `src/cozmo_companion/core/companion_legacy.py:2668`<br>`src/cozmo_companion/core/companion_legacy.py:937`<br>`src/cozmo_companion/core/companion_legacy.py:940` |
| `ESPIRITO_POS_ANIM_S` | `'12'`, `'8'` | `src/cozmo_companion/core/companion_legacy.py:2204`<br>`src/cozmo_companion/core/limites.py:39` |
| `ESPIRITO_POS_TTS_S` | `'25'`, `'35'` | `src/cozmo_companion/core/companion_legacy.py:409`<br>`src/cozmo_companion/core/companion_legacy.py:1792`<br>`src/cozmo_companion/core/companion_legacy.py:1875`<br>`src/cozmo_companion/core/companion_legacy.py:1834`<br>`src/cozmo_companion/core/companion_legacy.py:1856`<br>`src/cozmo_companion/core/companion_legacy.py:1845`<br>`src/cozmo_companion/core/companion_voz.py:132` |
| `ESPIRITO_SAIDA_DELAY_S` | `'15'` | `src/cozmo_companion/core/companion_legacy.py:2199` |
| `ESPONTANEO_ENABLED` | `'1'` | `src/cozmo_companion/core/companion_voz.py:583` |
| `FACE_BODY_MAX_S` | `'1.0'` | `src/cozmo_companion/core/face_watch.py:49` |
| `FACE_BODY_START` | `'0.14'` | `src/cozmo_companion/core/face_watch.py:43` |
| `FACE_BODY_VEL` | `'18'` | `src/cozmo_companion/core/face_watch.py:44` |
| `FACE_CORPO_MESA` | `'0'` | `src/cozmo_companion/core/face_watch.py:48` |
| `FACE_DEADBAND_X` | `'0.07'` | `src/cozmo_companion/core/face_watch.py:41` |
| `FACE_DEADBAND_Y` | `'0.06'` | `src/cozmo_companion/core/face_watch.py:42` |
| `FACE_EXTEND_S` | `'2.0'` | `src/cozmo_companion/core/face_watch.py:45` |
| `FACE_FRAME_BASE_S` | `'0.55'` | `src/cozmo_companion/core/face_watch.py:38` |
| `FACE_FRAME_S` | `'0.18'` | `src/cozmo_companion/core/face_watch.py:37`<br>`src/cozmo_companion/core/perf.py:49` |
| `FACE_MOTION_DIFF` | `'18'` | `src/cozmo_companion/core/face_watch.py:411` |
| `FACE_PERDIDO_S` | `'2.5'` | `src/cozmo_companion/core/face_watch.py:46` |
| `FACE_SCAN_CHANCE` | `'0.35'`, `'0.85'` | `src/cozmo_companion/core/face_watch.py:47`<br>`src/cozmo_companion/core/perf.py:50` |
| `FACE_SMOOTH` | `'0.42'` | `src/cozmo_companion/core/face_watch.py:40` |
| `FACE_TRACK_MIN_S` | `'0.10'` | `src/cozmo_companion/core/face_watch.py:39` |
| `FALANDO_SONO_EXT_S` | `'25'` | `src/cozmo_companion/core/vida.py:666` |
| `FALA_PROATIVA` | `'0'` | `src/cozmo_companion/core/perf.py:44` |
| `GAME_CHECK_S` | `'8'` | `src/cozmo_companion/core/perf.py:98` |
| `GAME_FACE_FRAME_S` | `'1.2'` | `src/cozmo_companion/core/perf.py:70` |
| `GAME_FACE_SCAN_CHANCE` | `'0.35'` | `src/cozmo_companion/core/perf.py:71` |
| `GAME_GPU_PERCENT` | `'70'` | `src/cozmo_companion/core/perf.py:97` |
| `GAME_IDLE_MULT` | `'4'` | `src/cozmo_companion/core/perf.py:75` |
| `GAME_LOOP_SLEEP` | `'1.2'` | `src/cozmo_companion/core/perf.py:67` |
| `GAME_MODE_STREAK` | `'2'` | `src/cozmo_companion/core/perf.py:169` |
| `GAME_NICE_EXTRA` | `'8'` | `src/cozmo_companion/core/perf.py:74` |
| `GAME_PROCESSES` | `'Gw2-64.exe,gw2-64.exe,Guild Wars 2'` | `src/cozmo_companion/core/perf.py:92` |
| `GAME_REQUIRE_GPU` | `'0'` | `src/cozmo_companion/core/perf.py:99` |
| `GAME_STT_BLOCKSIZE` | `'8000'` | `src/cozmo_companion/core/perf.py:73` |
| `GAME_STT_RMS` | `'140'` | `src/cozmo_companion/core/perf.py:72` |
| `GOV_BUDGET_INICIAL` | `'18'` | `src/cozmo_companion/core/governador.py:80` |
| `GOV_BURST` | `'22'` | `src/cozmo_companion/core/governador.py:81` |
| `GOV_EMA_ALPHA` | `'0.35'` | `src/cozmo_companion/core/governador.py:221` |
| `GOV_LOG_S` | `'20'` | `src/cozmo_companion/core/governador.py:305` |
| `GOV_MIN_ANIM_S` | `'3'` | `src/cozmo_companion/core/governador.py:78` |
| `GOV_PPCLIP_DTX_OK` | `str(network_tuning().base_tx_stall)` | `src/cozmo_companion/core/cozmo01_recovery.py:35`<br>`src/cozmo_companion/core/governador.py:238` |
| `GOV_PPCLIP_TX_IDLE_DELTA` | `'80'` | `src/cozmo_companion/core/conexao.py:652` |
| `GOV_RATIO_PREVENCAO` | `str(lim.udp_ratio_leve * 0.88)` | `src/cozmo_companion/core/governador.py:97` |
| `GOV_REFILL_AMARELO` | `'7'` | `src/cozmo_companion/core/governador.py:128` |
| `GOV_REFILL_LARANJA` | `'3'` | `src/cozmo_companion/core/governador.py:129` |
| `GOV_REFILL_VERDE` | `'14'` | `src/cozmo_companion/core/governador.py:127` |
| `GOV_REFILL_VERMELHO` | `'1'` | `src/cozmo_companion/core/governador.py:130` |
| `GOV_RX_IDLE_RATIO_MAX` | `'0.95'` | `src/cozmo_companion/core/conexao.py:642`<br>`src/cozmo_companion/core/conexao.py:745` |
| `GOV_RX_RATIO_ALTO` | `'2.0'` | `src/cozmo_companion/core/conexao.py:786`<br>`src/cozmo_companion/core/conexao.py:643` |
| `GOV_TX_DELTA_STALL` | `'120'`, `'180'`, `'400'` | `src/cozmo_companion/core/conexao.py:626`<br>`src/cozmo_companion/core/conexao.py:339`<br>`src/cozmo_companion/core/governador.py:233`<br>`src/cozmo_companion/core/governador.py:300` |
| `GOV_TX_IDLE_DELTA` | `'50'` | `src/cozmo_companion/core/conexao.py:627` |
| `GOV_WIFI_PROBE_S` | `'90'` | `src/cozmo_companion/core/governador.py:94` |
| `GUARDIAN_BOOT_GRACE_S` | `'180'` | `src/cozmo_companion/guardian/core/policy.py:91` |
| `GUARDIAN_HEALTH_STALE_S` | `'240'` | `src/cozmo_companion/guardian/core/policy.py:90` |
| `GUARDIAN_INTERVAL_S` | `'20'` | `src/cozmo_companion/guardian/__main__.py:51` |
| `GUARDIAN_LOG_TRIM_S` | `'86400'` | `src/cozmo_companion/guardian/core/manutencao.py:18` |
| `GUARDIAN_RESTART_DEAD_S` | `'120'` | `src/cozmo_companion/guardian/core/policy.py:82` |
| `GUARDIAN_SESSAO_FRESH_S` | `'300'` | `src/cozmo_companion/guardian/core/policy.py:105` |
| `GUARDIAN_WIFI_COOLDOWN_S` | `'25'` | `src/cozmo_companion/guardian/core/policy.py:119` |
| `INVOCATION_ID` | `None` | `src/cozmo_companion/guardian/__main__.py:26` |
| `LATIDO_COOLDOWN_S` | `'4'` | `src/cozmo_companion/core/companion_voz.py:663` |
| `LLM_ACOES` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:2117`<br>`src/cozmo_companion/core/companion_legacy.py:1657`<br>`src/cozmo_companion/core/companion_legacy.py:2074`<br>`src/cozmo_companion/core/companion_voz.py:893`<br>`src/cozmo_companion/voice/chat.py:63` |
| `LOOP_SLEEP` | `'0.15'`, `'0.25'` | `src/cozmo_companion/core/companion.py:1780`<br>`src/cozmo_companion/core/perf.py:46` |
| `LOUD_RMS` | `'5200'` | `src/cozmo_companion/voice/stt.py:32` |
| `MESA_BUMP_DELTA` | `'2.2'` | `src/cozmo_companion/core/mesa.py:36` |
| `MESA_BUMP_MIN_WHEEL` | `'10'` | `src/cozmo_companion/core/mesa.py:37` |
| `MESA_EMERG_COOLDOWN` | `'3.0'` | `src/cozmo_companion/core/mesa.py:38` |
| `MESA_FACE_CHANCE` | `'0.65'` | `src/cozmo_companion/core/companion_legacy.py:523` |
| `MESA_FISICA_S` | `'1.2'` | `src/cozmo_companion/core/companion_legacy.py:910` |
| `MESA_FISICA_TICKS` | `'12'` | `src/cozmo_companion/core/companion_legacy.py:853` |
| `MESA_RECUO_VEL` | `'30'` | `src/cozmo_companion/core/mesa.py:35` |
| `MESA_VEL_MAX` | `'32'` | `src/cozmo_companion/core/mesa.py:34` |
| `MIC_DEVICE` | `'fifine'` | `src/cozmo_companion/voice/mic.py:146` |
| `MIC_NAME` | `'fifine'` | `src/cozmo_companion/voice/mic.py:147` |
| `MIC_YIELD_LOCKS` | `''` | `src/cozmo_companion/voice/mic.py:75` |
| `MOTOR_CANCEL_COOLDOWN_S` | `'3.0'` | `src/cozmo_companion/core/motors.py:26` |
| `MOTOR_MAX_S` | `'2.5'` | `src/cozmo_companion/core/motors.py:15` |
| `NOTIF_ANIM` | `'0'` | `src/cozmo_companion/notifications/core/handler.py:194` |
| `NOTIF_ANIM_S` | `'2.2'` | `src/cozmo_companion/notifications/core/handler.py:162` |
| `NOTIF_BASE_COOLDOWN_S` | `os.environ.get('NOTIF_COOLDOWN_S', '0.4')` | `src/cozmo_companion/notifications/core/policy.py:212` |
| `NOTIF_BLOCK_FILA_BUSY` | `'1'` | `src/cozmo_companion/notifications/core/handler.py:108` |
| `NOTIF_BLOCK_RX_STALL` | `'1'` | `src/cozmo_companion/notifications/core/policy.py:205` |
| `NOTIF_BLOCK_UDP_LEVE` | `'1'` | `src/cozmo_companion/notifications/core/policy.py:200` |
| `NOTIF_COOLDOWN_S` | `'0.4'` | `src/cozmo_companion/notifications/core/policy.py:218`<br>`src/cozmo_companion/notifications/core/policy.py:214` |
| `NOTIF_ENABLED` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:2579`<br>`src/cozmo_companion/core/companion_voz.py:984`<br>`src/cozmo_companion/notifications/core/policy.py:171` |
| `NOTIF_FILA_PAUSE_S` | `'0.1'` | `src/cozmo_companion/notifications/core/handler.py:187` |
| `NOTIF_GESTO` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:1377`<br>`src/cozmo_companion/core/companion_legacy.py:1356` |
| `NOTIF_HOLD_MARGIN_S` | `'0.5'` | `src/cozmo_companion/notifications/core/handler.py:165` |
| `NOTIF_HOLD_MAX_S` | `'12'` | `src/cozmo_companion/notifications/core/handler.py:168` |
| `NOTIF_IGNORE_DURING_TTS` | `'1'` | `src/cozmo_companion/notifications/core/policy.py:195` |
| `NOTIF_LOOP_STOP_S` | `'0.25'` | `src/cozmo_companion/core/fila_cozmo.py:338` |
| `NOTIF_NA_BASE` | `'1'` | `src/cozmo_companion/notifications/core/policy.py:192` |
| `NOTIF_OLED_APP_S` | `'3'`, `os.environ.get('NOTIF_TELA_S', '4')` | `src/cozmo_companion/notifications/core/display.py:32`<br>`src/cozmo_companion/notifications/core/display.py:25` |
| `NOTIF_OLED_NA_BASE` | `'1'` | `src/cozmo_companion/core/fila_cozmo.py:346` |
| `NOTIF_OLED_PRIMEIRO` | `'1'` | `src/cozmo_companion/core/fila_cozmo.py:323` |
| `NOTIF_OLED_TITULO_S` | `str(max(2.0, total - app_s))` | `src/cozmo_companion/notifications/core/display.py:33` |
| `NOTIF_PAUSE_LOOP_S` | `'4'` | `src/cozmo_companion/notifications/core/handler.py:166` |
| `NOTIF_PC_AUDIO` | `'0'` | `src/cozmo_companion/notifications/core/som.py:61` |
| `NOTIF_PC_BEEP` | `'0'` | `src/cozmo_companion/notifications/core/som.py:62` |
| `NOTIF_PC_BEEP_VOLUME` | `'65536'` | `src/cozmo_companion/notifications/core/som.py:76` |
| `NOTIF_POST_QUIET_S` | `'6'`, `os.environ.get('NOTIF_UDP_QUIET_S', '8')` | `src/cozmo_companion/core/fila_cozmo.py:648`<br>`src/cozmo_companion/core/fila_cozmo.py:627` |
| `NOTIF_QUIET_S` | `'1.0'` | `src/cozmo_companion/core/fila_cozmo.py:357` |
| `NOTIF_RX_PAUSE_S` | `'18'` | `src/cozmo_companion/notifications/core/handler.py:115` |
| `NOTIF_SCROLL` | `'0'` | `src/cozmo_companion/core/fila_cozmo.py:351` |
| `NOTIF_SCROLL_PASSO_S` | `'0.85'`, `'1.0'` | `src/cozmo_companion/core/companion_legacy.py:1363`<br>`src/cozmo_companion/core/fila_cozmo.py:369` |
| `NOTIF_SCROLL_S` | `'14'` | `src/cozmo_companion/core/companion_legacy.py:1345` |
| `NOTIF_SINAL_PRIMEIRO` | `'0'` | `src/cozmo_companion/core/fila_cozmo.py:326` |
| `NOTIF_SOM` | `'1'` | `src/cozmo_companion/notifications/core/handler.py:73` |
| `NOTIF_SOM_AMP` | `'15000'` | `src/cozmo_companion/core/som_notif.py:37` |
| `NOTIF_SOM_DRAIN_S` | `os.environ.get('TTS_DRAIN_S', '0.9')` | `src/cozmo_companion/notifications/core/som.py:154` |
| `NOTIF_SOM_FREQ_HZ` | `'880'` | `src/cozmo_companion/core/som_notif.py:36` |
| `NOTIF_SOM_MANTER_FACE` | `'1'` | `src/cozmo_companion/core/companion_voz.py:372` |
| `NOTIF_SOM_MODO` | `None` | `src/cozmo_companion/core/fila_cozmo.py:388`<br>`src/cozmo_companion/notifications/core/handler.py:66` |
| `NOTIF_SOM_PACOTES` | `'3'`, `'4'` | `src/cozmo_companion/core/som_notif.py:35`<br>`src/cozmo_companion/notifications/core/som.py:51` |
| `NOTIF_SOM_PAUSA_S` | `'0.04'` | `src/cozmo_companion/notifications/core/som.py:141` |
| `NOTIF_SOM_PRIMEIRO` | `os.environ.get('NOTIF_SINAL_PRIMEIRO', '0')` | `src/cozmo_companion/core/fila_cozmo.py:326` |
| `NOTIF_SOM_RESPIRO_S` | `'0.1'` | `src/cozmo_companion/notifications/core/som.py:142` |
| `NOTIF_SOM_S` | `'0.65'` | `src/cozmo_companion/core/companion_voz.py:380`<br>`src/cozmo_companion/core/fila_cozmo.py:539`<br>`src/cozmo_companion/notifications/core/handler.py:164` |
| `NOTIF_TELA_S` | `'4'`, `'8'` | `src/cozmo_companion/core/companion_legacy.py:1343`<br>`src/cozmo_companion/notifications/core/display.py:31`<br>`src/cozmo_companion/notifications/core/display.py:27` |
| `NOTIF_TTS_MANTER_FACE` | `'0'` | `src/cozmo_companion/core/companion_voz.py:290` |
| `NOTIF_TTS_PACOTES` | `'3'` | `src/cozmo_companion/core/companion_voz.py:324` |
| `NOTIF_TTS_QUIET_S` | `os.environ.get('COZMO_TTS_SINAL_QUIET_S', '6')` | `src/cozmo_companion/core/companion_voz.py:340`<br>`src/cozmo_companion/core/fila_cozmo.py:597` |
| `NOTIF_UDP_QUIET_S` | `'10'`, `'8'` | `src/cozmo_companion/core/fila_cozmo.py:629`<br>`src/cozmo_companion/notifications/core/handler.py:207` |
| `OLLAMA_GAME_MAX_TOKENS` | `'35'` | `src/cozmo_companion/core/perf.py:76` |
| `OLLAMA_GAME_THREADS` | `'1'` | `src/cozmo_companion/core/perf.py:78` |
| `OLLAMA_GAME_TIMEOUT_S` | `'15'` | `src/cozmo_companion/core/perf.py:77` |
| `OLLAMA_KEEP_ALIVE` | `'10m'` | `src/cozmo_companion/voice/chat.py:58` |
| `OLLAMA_MAX_TOKENS` | `'24'`, `'70'`, `'80'` | `src/cozmo_companion/core/companion_legacy.py:533`<br>`src/cozmo_companion/core/perf.py:55`<br>`src/cozmo_companion/voice/chat.py:55` |
| `OLLAMA_MODEL` | `'llama3.2:1b'` | `src/cozmo_companion/core/companion.py:108`<br>`src/cozmo_companion/core/companion_legacy.py:218` |
| `OLLAMA_THREADS` | `'2'`, `'4'` | `src/cozmo_companion/core/companion_legacy.py:535`<br>`src/cozmo_companion/core/perf.py:57`<br>`src/cozmo_companion/voice/chat.py:57` |
| `OLLAMA_TIMEOUT_S` | `'20'`, `'30'`, `'45'` | `src/cozmo_companion/core/companion_legacy.py:534`<br>`src/cozmo_companion/core/perf.py:56`<br>`src/cozmo_companion/voice/chat.py:56` |
| `OLLAMA_URL` | `'http://127.0.0.1:11434'` | `src/cozmo_companion/core/companion.py:107`<br>`src/cozmo_companion/core/companion_legacy.py:217` |
| `PERCEPTION_ANIM_COOLDOWN_S` | `'18'` | `src/cozmo_companion/core/companion.py:317` |
| `PET_LIVRE_CAMERA_START_S` | `'10'` | `src/cozmo_companion/core/companion.py:614` |
| `PET_LIVRE_MAX_S` | `'11'` | `src/cozmo_companion/core/pet_livre.py:70` |
| `PET_LIVRE_MIN_S` | `'4'` | `src/cozmo_companion/core/pet_livre.py:69` |
| `PET_LIVRE_START_S` | `'1.2'` | `src/cozmo_companion/core/companion.py:617`<br>`src/cozmo_companion/core/pet_livre.py:52` |
| `PET_READY_MAX_S` | `'18'` | `src/cozmo_companion/core/pet_livre.py:73` |
| `PET_READY_MIN_S` | `'8'` | `src/cozmo_companion/core/pet_livre.py:72` |
| `PROACTIVE_LLM` | `'0'` | `src/cozmo_companion/voice/chat.py:322` |
| `PROACTIVE_SAIDA_DELAY_S` | `'60'` | `src/cozmo_companion/core/companion_legacy.py:2450` |
| `PULSE_ANIM_CHANCE` | `'0.35'` | `src/cozmo_companion/core/companion.py:1485` |
| `REACAO_OFICIAL_ENABLED` | `'1'` | `src/cozmo_companion/core/companion_voz.py:574` |
| `SEMPRE_PULSE_S` | `'15'`, `'16'` | `src/cozmo_companion/core/companion.py:1468`<br>`src/cozmo_companion/core/companion_legacy.py:2249` |
| `SEMPRE_VIVO` | `'1'` | `src/cozmo_companion/core/charger.py:871`<br>`src/cozmo_companion/core/companion_legacy.py:486`<br>`src/cozmo_companion/core/companion_legacy.py:2277`<br>`src/cozmo_companion/core/vida.py:461`<br>`src/cozmo_companion/core/vida.py:736`<br>`src/cozmo_companion/core/vida.py:737`<br>`src/cozmo_companion/core/vida.py:738`<br>`src/cozmo_companion/core/vida.py:739` |
| `SLEEP_MAX_S` | `'3000'` | `src/cozmo_companion/core/vida.py:39` |
| `SLEEP_MIN_S` | `'1800'` | `src/cozmo_companion/core/vida.py:38` |
| `SOM_REACAO_ENABLED` | `'1'` | `src/cozmo_companion/core/som_reacao.py:125` |
| `SOM_REACAO_PACOTES` | `'14'` | `src/cozmo_companion/core/som_reacao.py:87` |
| `SOM_REACAO_PAUSA_S` | `'0.006'` | `src/cozmo_companion/core/som_reacao.py:153` |
| `SOM_REACAO_QUIET_S` | `'2.5'` | `src/cozmo_companion/core/companion_voz.py:629` |
| `SOM_REACAO_RESPIRO_S` | `'0.025'` | `src/cozmo_companion/core/som_reacao.py:154` |
| `SOM_REACAO_RX_PAUSE_S` | `'8'` | `src/cozmo_companion/core/companion_voz.py:622` |
| `SOM_REACAO_VOLUME_BOOST` | `'8000'` | `src/cozmo_companion/core/som_reacao.py:133` |
| `SONOLENTO_MAX_S` | `'240'` | `src/cozmo_companion/core/vida.py:85` |
| `SONOLENTO_MIN_S` | `'90'` | `src/cozmo_companion/core/vida.py:84` |
| `SONO_AUTO` | `'1'` | `src/cozmo_companion/core/vida.py:113` |
| `SONO_LOOP_MAX_S` | `'300'` | `src/cozmo_companion/core/vida.py:104` |
| `SONO_LOOP_MIN_S` | `'90'` | `src/cozmo_companion/core/vida.py:103` |
| `SONO_OLED_REFRESH_S` | `'0.8'`, `'1.0'`, `'18'` | `src/cozmo_companion/core/motor_cozmo.py:433`<br>`src/cozmo_companion/core/motor_cozmo.py:338`<br>`src/cozmo_companion/display/face.py:145` |
| `SONO_PPCLIP_LOOP_MIN_S` | `'45'` | `src/cozmo_companion/core/motor_cozmo.py:345` |
| `SONO_PPCLIP_SEMEAR_S` | `os.environ.get('SONO_OLED_REFRESH_S', '18')` | `src/cozmo_companion/core/motor_cozmo.py:338` |
| `SONO_RONCO_CHANCE` | `'0.45'` | `src/cozmo_companion/core/vida.py:102` |
| `SONO_RONCO_MAX_S` | `'480'` | `src/cozmo_companion/core/vida.py:101` |
| `SONO_RONCO_MIN_S` | `'120'` | `src/cozmo_companion/core/vida.py:100` |
| `SONO_TELA_ESCURA` | `'0'` | `src/cozmo_companion/core/companion.py:711`<br>`src/cozmo_companion/core/companion.py:939`<br>`src/cozmo_companion/core/motor_cozmo.py:199`<br>`src/cozmo_companion/core/motor_cozmo.py:1133`<br>`src/cozmo_companion/core/motor_cozmo.py:209`<br>`src/cozmo_companion/core/vida.py:114` |
| `STT_BLOCKSIZE` | `'4000'` | `src/cozmo_companion/core/perf.py:52` |
| `STT_COOLDOWN_S` | `'2.5'` | `src/cozmo_companion/voice/stt.py:157` |
| `STT_MIC_RETRY_S` | `'2.5'` | `src/cozmo_companion/voice/stt.py:246` |
| `STT_MIN_CHARS_BASE` | `'8'` | `src/cozmo_companion/core/companion_legacy.py:1494` |
| `STT_PARTIAL_MIN` | `'2'` | `src/cozmo_companion/voice/stt.py:201` |
| `STT_PAUSE_DURING_TTS` | `'0'`, `'1'` | `src/cozmo_companion/core/companion_legacy.py:334`<br>`src/cozmo_companion/core/companion_legacy.py:1754`<br>`src/cozmo_companion/core/companion_voz.py:319`<br>`src/cozmo_companion/core/companion_voz.py:418`<br>`src/cozmo_companion/voice/stt.py:82` |
| `STT_RMS` | `'25'`, `'4'`, `'5'` | `src/cozmo_companion/core/companion_legacy.py:566`<br>`src/cozmo_companion/core/companion_voz.py:176`<br>`src/cozmo_companion/core/perf.py:51`<br>`src/cozmo_companion/voice/stt.py:31` |
| `STT_RMS_BASE` | `'3'` | `src/cozmo_companion/core/companion_legacy.py:532`<br>`src/cozmo_companion/core/companion_legacy.py:556`<br>`src/cozmo_companion/core/companion_legacy.py:560`<br>`src/cozmo_companion/core/companion_voz.py:166`<br>`src/cozmo_companion/core/companion_voz.py:170` |
| `STT_RMS_IDLE_BASE` | `'42'` | `src/cozmo_companion/core/companion_legacy.py:558`<br>`src/cozmo_companion/core/companion_voz.py:168` |
| `TELA_ACORDOU_S` | `'8'` | `src/cozmo_companion/core/vida.py:215` |
| `TELA_ESPIRITO_S` | `'9'` | `src/cozmo_companion/core/companion_legacy.py:2104`<br>`src/cozmo_companion/core/companion_legacy.py:2137`<br>`src/cozmo_companion/core/companion_legacy.py:2169` |
| `TELA_GUARD_S` | `'4'` | `src/cozmo_companion/display/face.py:170` |
| `TELA_MIN_S` | `'6'` | `src/cozmo_companion/display/face.py:25` |
| `TELA_NA_BASE` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:2480` |
| `TELA_RESPOSTA_S` | `'6'`, `'8'` | `src/cozmo_companion/core/companion_legacy.py:1177`<br>`src/cozmo_companion/core/companion_legacy.py:1007`<br>`src/cozmo_companion/core/companion_voz.py:500`<br>`src/cozmo_companion/core/companion_voz.py:212` |
| `TELA_SCROLL_PASSO_S` | `'0.85'` | `src/cozmo_companion/display/face.py:26` |
| `TTS_AUDIO_NA_BASE` | `'1'` | `src/cozmo_companion/voice/sinal.py:38` |
| `TTS_CACHE_MAX` | `'64'` | `src/cozmo_companion/voice/tts.py:259` |
| `TTS_CHUNK_PACOTES` | `'1'`, `'3'`, `str(CHUNK_PACOTES)` | `src/cozmo_companion/core/limites.py:42`<br>`src/cozmo_companion/voice/tts.py:27`<br>`src/cozmo_companion/voice/tts.py:324` |
| `TTS_CHUNK_PAUSA_S` | `'1.4'`, `'1.6'`, `'4.0'`, `str(CHUNK_PAUSA_S)` | `src/cozmo_companion/core/limites.py:43`<br>`src/cozmo_companion/voice/tts.py:28`<br>`src/cozmo_companion/voice/tts.py:322`<br>`src/cozmo_companion/voice/tts.py:325` |
| `TTS_DRAIN_S` | `'0.9'`, `'1.8'` | `src/cozmo_companion/notifications/core/som.py:154`<br>`src/cozmo_companion/voice/tts.py:442` |
| `TTS_ESPEAK_RATE` | `'175'` | `src/cozmo_companion/voice/tts.py:30` |
| `TTS_FACE_OFF` | `'1'` | `src/cozmo_companion/voice/tts.py:353` |
| `TTS_MAX_PACOTES` | `'1'`, `'8'` | `src/cozmo_companion/core/limites.py:41`<br>`src/cozmo_companion/voice/tts.py:378` |
| `TTS_MAX_PACOTES_BASE` | `'1'` | `src/cozmo_companion/core/limites.py:40` |
| `TTS_MODO` | `'sinal'` | `src/cozmo_companion/voice/sinal.py:42`<br>`src/cozmo_companion/voice/tts.py:86`<br>`src/cozmo_companion/voice/tts.py:313`<br>`src/cozmo_companion/voice/tts.py:382` |
| `TTS_NA_BASE` | `'0'` | `src/cozmo_companion/core/companion_legacy.py:1014`<br>`src/cozmo_companion/core/companion_voz.py:219` |
| `TTS_PACKET_MS` | `'35'` | `src/cozmo_companion/voice/tts.py:29` |
| `TTS_PING_INTERVAL_S` | `'0.75'` | `src/cozmo_companion/voice/tts.py:279` |
| `TTS_RX_RETRY` | `'3'` | `src/cozmo_companion/voice/tts.py:90` |
| `TTS_SINAL_AMP` | `'14500'` | `src/cozmo_companion/voice/tts.py:194` |
| `TTS_SINAL_AUDIO` | `'0'` | `src/cozmo_companion/voice/tts.py:328`<br>`src/cozmo_companion/voice/tts.py:359` |
| `TTS_SINAL_MANTEM_FACE_BASE` | `'1'` | `src/cozmo_companion/core/companion_voz.py:407`<br>`src/cozmo_companion/core/companion_voz.py:292`<br>`src/cozmo_companion/core/fila_cozmo.py:584`<br>`src/cozmo_companion/core/fila_cozmo.py:589` |
| `TTS_SINAL_MAX_CHARS` | `'10'` | `src/cozmo_companion/core/fila_cozmo.py:171`<br>`src/cozmo_companion/voice/sinal.py:80` |
| `TTS_SINAL_PACOTES` | `'1'`, `'6'` | `src/cozmo_companion/core/companion_legacy.py:338`<br>`src/cozmo_companion/core/companion_legacy.py:1767`<br>`src/cozmo_companion/core/companion_voz.py:326`<br>`src/cozmo_companion/core/companion_voz.py:423`<br>`src/cozmo_companion/voice/tts.py:193`<br>`src/cozmo_companion/voice/tts.py:387` |
| `TTS_SINAL_PADRAO` | `'Beep'` | `src/cozmo_companion/voice/sinal.py:59` |
| `TTS_SINAL_PAUSA_S` | `'0.8'` | `src/cozmo_companion/voice/tts.py:409` |
| `TTS_SINAL_VOZ` | `'0'` | `src/cozmo_companion/voice/tts.py:360` |
| `TTS_TAIL_S` | `'0.35'` | `src/cozmo_companion/voice/tts.py:291` |
| `TTS_UDP_GRACE_S` | `'18'` | `src/cozmo_companion/core/limites.py:44` |
| `UTIL_TELA_LINK_GRACE_S` | `'35'` | `src/cozmo_companion/core/companion_legacy.py:424` |
| `UTIL_VOZ_COOLDOWN_S` | `'12'` | `src/cozmo_companion/core/companion_voz.py:547` |
| `VOSK_MODEL` | `'/mnt/G/PROJETOS/cozmo-companion/data/vosk-model-small-pt-0.3'` | `src/cozmo_companion/core/companion_legacy.py:2554`<br>`src/cozmo_companion/core/companion_voz.py:959` |
| `WAKE_BASE_VISUAL_ONLY` | `'1'` | `src/cozmo_companion/core/companion_voz.py:468` |
| `WAKE_CAMERA_BASE` | `'0'` | `src/cozmo_companion/core/vida.py:249` |
| `WAKE_NA_BASE_RELAX` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:1147`<br>`src/cozmo_companion/core/companion_legacy.py:1464`<br>`src/cozmo_companion/core/companion_voz.py:476` |
| `WAKE_OBRIGATORIO` | `'0'` | `src/cozmo_companion/voice/intent.py:157` |
| `WAKE_RELAX` | `'1'` | `src/cozmo_companion/core/companion_legacy.py:1502`<br>`src/cozmo_companion/core/companion_voz.py:748` |
| `WAKE_TIMEOUT_S` | `'12'`, `'9'` | `src/cozmo_companion/core/companion_legacy.py:434`<br>`src/cozmo_companion/core/companion_voz.py:142`<br>`src/cozmo_companion/voice/wake.py:133` |
| `WAKE_VOSK_ALIASES` | `'oração,oracao'` | `src/cozmo_companion/voice/wake.py:26` |
| `WAKE_WORDS` | `'cozmo,cosmo'` | `src/cozmo_companion/voice/wake.py:17` |
| `WEATHER_CACHE_S` | `600` | `src/cozmo_companion/weather/bage.py:31` |
| `XDG_DATA_DIRS` | `'/usr/local/share:/usr/share'` | `src/cozmo_companion/notifications/core/apps.py:75` |
| `XDG_RUNTIME_DIR` | `f'/run/user/{os.getuid()}'` | `src/cozmo_companion/voice/mic.py:84` |

Total: **542** variáveis.
