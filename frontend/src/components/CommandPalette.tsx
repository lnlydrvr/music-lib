/* ⌘K-палитра команд (cmdk): переходы по экранам, тема, таблица клавиш.
   Открытое состояние — в overlays-сторе (подавление хоткеев в hotkeys.ts),
   Esc/клик вне закрывает Radix-диалог cmdk из коробки. */
import { Command } from "cmdk";
import { useOverlays } from "../stores/overlays";
import { useTheme } from "../hooks/useTheme";
import { NAV_ITEMS } from "../nav";
import { useTranslation } from "react-i18next";

export function CommandPalette() {
  const { t } = useTranslation();
  const open = useOverlays((s) => s.commandOpen);
  const setCommandOpen = useOverlays((s) => s.setCommandOpen);
  const setKeymapOpen = useOverlays((s) => s.setKeymapOpen);
  const { toggle } = useTheme();

  /* Выбор пункта: сначала закрыть палитру, потом действие. */
  const run = (fn: () => void) => {
    setCommandOpen(false);
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setCommandOpen}
      label={t("shell.command.label")}
      overlayClassName="cmdk-overlay"
      contentClassName="cmdk"
      loop
    >
      <Command.Input placeholder={t("shell.command.search")} autoFocus />
      <Command.List>
        <Command.Empty>{t("shell.command.empty")}</Command.Empty>
        <Command.Group heading={t("shell.command.navigate")}>
          {NAV_ITEMS.map((item) => (
            <Command.Item
              key={item.route}
              onSelect={() => run(() => {
                location.hash = "#/" + item.route;
              })}
            >
              {t(item.labelKey)}
              <span className="kbd">{item.key}</span>
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Separator />
        <Command.Group heading={t("shell.command.actions")}>
          <Command.Item onSelect={() => run(toggle)}>
            {t("shell.theme.switch")}
            <span className="kbd">t</span>
          </Command.Item>
          <Command.Item
            onSelect={() =>
              run(() => {
                setKeymapOpen(true);
              })
            }
          >
            {t("dialogs.keymap.title")}
            <span className="kbd">?</span>
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
