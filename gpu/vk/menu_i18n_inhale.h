// (inhale) The Insert menu's translations that are this fork's own: the texts of vk_menu.cpp that upstream's menu does
// not have, in each language of menu_i18n.h. They are here and not in menu_i18n.h so that that file stays upstream's,
// row for row: a sync then merges upstream's new rows and counts with nothing of this fork's in the way.
// vk_menu_i18n.cpp reads a language's rows there, then its rows here. Sorted by the English text, as there.
// Machine-made translations, as there.
#pragma once

#include "menu_i18n.h"

namespace mkwvk::menu_i18n::inhale {
// The texts of menu_i18n.h that this fork's menu no longer has (reworded or removed in vk_menu.cpp). Their rows stay
// there, never looked up. tests/test_menu_i18n.py reads this list; when upstream drops one, drop it here.
inline constexpr const char* kRetired[] = {
    "And a graph of the last 4 seconds' frame times, with a line at the Game frame rate cap's.",
    "What the ocarina hears when the game's microphone option is on (playing an instrument, or humming).",
};
inline constexpr Entry kpt_BR[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "E um gráfico dos tempos de quadro dos últimos 4 segundos, com uma linha no tempo do limite de fps."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Nitidez 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Controle: o direcional move, A atribui, B volta."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Nitidez 30%, o perfil Portátil."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Nitidez 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Nitidez 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Ajusta o Filtro de escala, a Nitidez e o Perfil para uma GPU com essa memória. A Geração de quadros continua sendo escolha sua."},
    {"The microphone the game listens to, when it uses one.", "O microfone que o jogo escuta, quando usa um."},
};
inline constexpr Entry kes_419[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "Y un gráfico de los tiempos de cuadro de los últimos 4 segundos, con una línea en el tiempo del límite de fps."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Nitidez 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Control: la cruceta mueve, A asigna, B vuelve."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Nitidez 30%, el perfil Portátil."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Nitidez 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Nitidez 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Ajusta el Filtro de escalado, la Nitidez y el Perfil para una GPU con esa memoria. La Generación de cuadros sigue siendo elección tuya."},
    {"The microphone the game listens to, when it uses one.", "El micrófono que escucha el juego, cuando usa uno."},
};
inline constexpr Entry kes[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "Y un gráfico de los tiempos de fotograma de los últimos 4 segundos, con una línea en el tiempo del límite de fps."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Nitidez 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Mando: la cruceta mueve, A asigna, B vuelve."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Nitidez 30%, el perfil Portátil."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Nitidez 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Nitidez 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Ajusta el Filtro de escalado, la Nitidez y el Perfil para una GPU con esa memoria. La Generación de fotogramas sigue siendo elección tuya."},
    {"The microphone the game listens to, when it uses one.", "El micrófono que escucha el juego, cuando usa uno."},
};
inline constexpr Entry kfr[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "Et un graphique des temps d'image des 4 dernières secondes, avec une ligne à celui de la limite d'images."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Netteté 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Manette : la croix déplace, A assigne, B revient."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Netteté 30%, le profil Portable."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Netteté 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Netteté 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Règle le Filtre d'échelle, la Netteté et le Profil pour un GPU doté d'autant de mémoire. La Génération d'images reste votre choix."},
    {"The microphone the game listens to, when it uses one.", "Le micro que le jeu écoute, quand il en utilise un."},
};
inline constexpr Entry kde[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "Dazu ein Graph der Frame-Zeiten der letzten 4 Sekunden, mit einer Linie beim FPS-Limit."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Schärfe 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Gamepad: D-Pad bewegt, A belegt, B geht zurück."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Schärfe 30%, das Handheld-Profil."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Schärfe 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Schärfe 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Stellt den Skalierungsfilter, die Schärfe und das Profil für eine GPU mit so viel Speicher ein. Die Frame-Generierung bleibt unverändert."},
    {"The microphone the game listens to, when it uses one.", "Das Mikrofon, auf das das Spiel hört, wenn es eins verwendet."},
};
inline constexpr Entry kit[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "E un grafico dei tempi dei fotogrammi degli ultimi 4 secondi, con una linea a quello del limite fps."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Nitidezza 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Controller: la croce sposta, A assegna, B torna indietro."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Nitidezza 30%, il profilo Portatile."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Nitidezza 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Nitidezza 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Imposta il Filtro di scala, la Nitidezza e il Profilo per una GPU con quella memoria. La Generazione fotogrammi resta a tua scelta."},
    {"The microphone the game listens to, when it uses one.", "Il microfono che il gioco ascolta, quando ne usa uno."},
};
inline constexpr Entry knl[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "En een grafiek van de frametijden van de laatste 4 seconden, met een lijn bij die van de framelimiet."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Scherpte 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Gamepad: D-pad beweegt, A wijst toe, B gaat terug."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Scherpte 30%, het Handheld-profiel."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Scherpte 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Scherpte 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Stelt het Schaalfilter, de Scherpte en het Profiel in voor een GPU met zoveel geheugen. Framegeneratie blijft jouw keuze."},
    {"The microphone the game listens to, when it uses one.", "De microfoon waarnaar het spel luistert, als het er een gebruikt."},
};
inline constexpr Entry kpl[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "Do tego wykres czasów klatek z ostatnich 4 sekund, z linią na poziomie limitu klatek."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, Ostrość 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Pad: krzyżak przesuwa, A przypisuje, B wraca."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, Ostrość 30%, profil przenośny."},
    {"Lanczos, Sharpness 40%.", "Lanczos, Ostrość 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, Ostrość 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Ustawia Filtr skalowania okna, Ostrość i Profil dla GPU z taką ilością pamięci. Generowanie klatek pozostaje twoim wyborem."},
    {"The microphone the game listens to, when it uses one.", "Mikrofon, którego słucha gra, gdy z niego korzysta."},
};
inline constexpr Entry kru[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "И график времени кадров за последние 4 секунды, с линией на уровне лимита кадров."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, резкость 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "Геймпад: крестовина — выбор, A — назначить, B — назад."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, резкость 30%, портативный профиль."},
    {"Lanczos, Sharpness 40%.", "Lanczos, резкость 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, резкость 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "Задаёт «Фильтр масштабирования», «Резкость» и «Профиль» для GPU с таким объёмом памяти. «Генерация кадров» остаётся на ваш выбор."},
    {"The microphone the game listens to, when it uses one.", "Микрофон, который слушает игра, когда он ей нужен."},
};
inline constexpr Entry kja[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "さらに、直近4秒間のフレームタイムのグラフを表示します。フレームレート上限の位置に線が引かれます。"},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom、シャープネス30%。"},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "コントローラー：十字キーで移動、Aで割り当て、Bで戻ります。"},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos、シャープネス30%、携帯モードのプロファイル。"},
    {"Lanczos, Sharpness 40%.", "Lanczos、シャープネス40%。"},
    {"Lanczos, Sharpness 50%.", "Lanczos、シャープネス50%。"},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "そのメモリー量のGPUに合わせて、拡大縮小フィルター、シャープネス、プロファイルを設定します。フレーム生成は変わりません。"},
    {"The microphone the game listens to, when it uses one.", "ゲームがマイクを使うときに、音を聞き取るマイクです。"},
};
inline constexpr Entry kko[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "여기에 최근 4초간의 프레임 시간 그래프도 표시하며, 프레임 제한 위치에 선을 긋습니다."},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom, 선명도 30%."},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "게임패드: 방향 버튼으로 이동, A로 지정, B로 뒤로 갑니다."},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos, 선명도 30%, 휴대 모드 프로필."},
    {"Lanczos, Sharpness 40%.", "Lanczos, 선명도 40%."},
    {"Lanczos, Sharpness 50%.", "Lanczos, 선명도 50%."},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "해당 메모리 용량의 GPU에 맞춰 창 스케일링 필터, 선명도, 프로필을 설정합니다. 프레임 생성은 직접 고른 대로 유지됩니다."},
    {"The microphone the game listens to, when it uses one.", "게임이 마이크를 사용할 때 소리를 듣는 마이크입니다."},
};
inline constexpr Entry kzh_Hans[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "另外显示最近4秒的帧时间图表，并在帧率上限处画一条线。"},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom、锐度30%。"},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "手柄：十字键移动，A绑定，B返回。"},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos，锐度30%，掌机模式配置。"},
    {"Lanczos, Sharpness 40%.", "Lanczos、锐度40%。"},
    {"Lanczos, Sharpness 50%.", "Lanczos、锐度50%。"},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "按该显存容量的GPU设置窗口缩放滤镜、锐度和配置。帧生成保持你的选择。"},
    {"The microphone the game listens to, when it uses one.", "游戏使用麦克风时所听取的麦克风。"},
};
inline constexpr Entry kzh_Hant[] = {
    {"And a graph of the last 4 seconds' frame times, with a line at the frame rate cap's.", "另外顯示最近4秒的畫格時間圖表，並在畫格率上限處畫一條線。"},
    {"Catmull-Rom, Sharpness 30%.", "Catmull-Rom、銳利度30%。"},
    {"Gamepad: the D-pad moves, A binds, B goes back.", "控制器：十字鍵移動，A綁定，B返回。"},
    {"Lanczos, Sharpness 30%, the Handheld Profile.", "Lanczos，銳利度30%，掌機模式設定檔。"},
    {"Lanczos, Sharpness 40%.", "Lanczos、銳利度40%。"},
    {"Lanczos, Sharpness 50%.", "Lanczos、銳利度50%。"},
    {"Sets the window scaling filter, the Sharpness and the Profile for a GPU with that much memory. Frame generation stays yours.", "依該顯示記憶體容量的GPU設定視窗縮放濾鏡、銳利度和設定檔。畫格生成維持你的選擇。"},
    {"The microphone the game listens to, when it uses one.", "遊戲使用麥克風時所聽取的麥克風。"},
};
// (the languages of menu_i18n.h's kLangs, in its order: vk_menu_i18n.cpp takes both by one index)
inline constexpr Lang kLangs[] = {
    {"en", "English", nullptr, 0},
    {"pt-BR", "Português (Brasil)", kpt_BR, sizeof kpt_BR / sizeof kpt_BR[0]},
    {"es-419", "Español (Latinoamérica)", kes_419, sizeof kes_419 / sizeof kes_419[0]},
    {"es", "Español (España)", kes, sizeof kes / sizeof kes[0]},
    {"fr", "Français", kfr, sizeof kfr / sizeof kfr[0]},
    {"de", "Deutsch", kde, sizeof kde / sizeof kde[0]},
    {"it", "Italiano", kit, sizeof kit / sizeof kit[0]},
    {"nl", "Nederlands", knl, sizeof knl / sizeof knl[0]},
    {"pl", "Polski", kpl, sizeof kpl / sizeof kpl[0]},
    {"ru", "Русский", kru, sizeof kru / sizeof kru[0]},
    {"ja", "日本語", kja, sizeof kja / sizeof kja[0]},
    {"ko", "한국어", kko, sizeof kko / sizeof kko[0]},
    {"zh-Hans", "简体中文", kzh_Hans, sizeof kzh_Hans / sizeof kzh_Hans[0]},
    {"zh-Hant", "繁體中文", kzh_Hant, sizeof kzh_Hant / sizeof kzh_Hant[0]},
};
static_assert(sizeof kLangs / sizeof kLangs[0] == kLangCount, "a language of menu_i18n.h has no table here");
}  // namespace mkwvk::menu_i18n::inhale
