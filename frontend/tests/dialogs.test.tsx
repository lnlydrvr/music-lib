import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider, useDialogs } from "../src/components/dialogs/DialogProvider";
import { KeymapDialog } from "../src/components/dialogs/KeymapDialog";
import { useOverlays } from "../src/stores/overlays";
import { changeLanguage } from "../src/i18n";

/* Тестовый стенд: кнопки дергают API диалогов, результат пишется в data-result. */
function Harness({ onResult }: { onResult: (r: unknown) => void }) {
  const d = useDialogs();
  return (
    <div>
      <button onClick={() => d.confirm("Точно удалить?").then(onResult)}>b-confirm</button>
      <button
        onClick={() =>
          d.confirm("Опасно?", { defaultOk: false }).then(onResult)
        }
      >
        b-confirm-cancel-first
      </button>
      <button onClick={() => d.prompt("Имя плейлиста", { value: "Микс" }).then(onResult)}>b-prompt</button>
      <button onClick={() => d.prompt("Legacy prompt", { value: "value" }).then(onResult)}>b-prompt-legacy</button>
      <button onClick={() => d.confirm({ code: "dialogs.confirm.title" }).then(onResult)}>b-confirm-descriptor</button>
      <button onClick={() => d.info({ code: "dialogs.confirm.title" }, { code: "dialogs.yes" }).then(onResult)}>b-info-descriptor</button>
      <button onClick={() => d.info("Legacy info", "Legacy OK").then(onResult)}>b-info-legacy</button>
      <button
        onClick={() =>
          d
            .pick("Выберите источники", [
              { label: "iTunes", sub: "быстрый" },
              { label: "Deezer" },
              { label: "Discogs" },
            ])
            .then(onResult)
        }
      >
        b-pick-one
      </button>
      <button
        onClick={() => d.pick("Legacy pick", [{ label: "Legacy option" }]).then(onResult)}
      >
        b-pick-legacy
      </button>
      <button
        onClick={() =>
          d
            .pick(
              "Треки",
              [{ label: "A" }, { label: "B" }, { label: "C" }],
              { multiple: true, defaultSelected: new Set([1]) },
            )
            .then(onResult)
        }
      >
        b-pick-many
      </button>
      <button
        onClick={() =>
          d
            .open({
              title: "Кастом",
              build: () => <div>custom-body</div>,
              actions: [{ title: "Сейв", onClick: async () => false }],
            })
            .then(onResult)
        }
      >
        b-open-stay
      </button>
      <button
        onClick={() =>
          d
            .open({
              title: "Кастом2",
              build: () => <div>custom-body-2</div>,
              actions: [{ title: "Сейв", onClick: async () => "saved" }],
            })
            .then(onResult)
        }
      >
        b-open-close
      </button>
      <button
        onClick={() =>
          d.open({
            title: { code: "dialogs.confirm.title" },
            build: () => <div>localized-body</div>,
            actions: [
              { title: { code: "dialogs.cancel" }, class: "ghost", value: null, ok: true },
              { title: { code: "dialogs.yes" }, value: true, ok: true },
            ],
          }).then(onResult)
        }
      >
        b-open-localized
      </button>
    </div>
  );
}

describe("DialogProvider", () => {
  it("confirm: «Да» → true, «Отмена»/Esc → false", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-confirm"));
    const dlg = screen.getByRole("dialog");
    expect(within(dlg).getByText("Точно удалить?")).toBeInTheDocument();
    await user.click(within(dlg).getByRole("button", { name: "Да" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(true));

    await user.click(screen.getByText("b-confirm"));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(false));
  });

  it("confirm defaultOk=false: «Отмена» первая и в фокусе", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-confirm-cancel-first"));
    const dlg = screen.getByRole("dialog");
    const buttons = within(dlg).getAllByRole("button").filter((b) => b.closest(".modal-actions"));
    expect(buttons[0]).toHaveTextContent("Отмена");
    await waitFor(() => expect(buttons[0]).toHaveFocus());
    // Enter на сфокусированной «Отмене» — безопасное действие.
    await user.keyboard("{Enter}");
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(false));
  });

  it("prompt: OK возвращает значение, отмена — null", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-prompt"));
    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("Микс");
    await user.clear(input);
    await user.type(input, "Новый микс");
    await user.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith("Новый микс"));

    await user.click(screen.getByText("b-prompt"));
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(null));
  });

  it("prompt: Enter в поле = OK", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);
    await user.click(screen.getByText("b-prompt"));
    await user.type(screen.getByRole("textbox"), "!");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(res).toHaveBeenLastCalledWith("Микс!"));
  });

  it("preserves the literal OK button for prompt, info, and pick after a locale change", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);
    await changeLanguage("ru");

    await user.click(screen.getByText("b-prompt-legacy"));
    expect(screen.getByRole("dialog")).toHaveTextContent("Legacy prompt");
    expect(screen.getByRole("button", { name: "OK" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(screen.getByText("b-info-legacy"));
    expect(screen.getByRole("dialog")).toHaveTextContent("Legacy info");
    expect(screen.getByRole("dialog")).toHaveTextContent("Legacy OK");
    await user.click(screen.getByRole("button", { name: "OK" }));

    await user.click(screen.getByText("b-pick-legacy"));
    expect(screen.getByRole("dialog")).toHaveTextContent("Legacy pick");
    expect(screen.getByRole("radio", { name: "Legacy option" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "OK" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
  });

  it("pick single: индекс выбора, пустой выбор — null", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-pick-one"));
    await user.click(screen.getByRole("radio", { name: /Deezer/ }));
    await user.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(1));

    await user.click(screen.getByText("b-pick-one"));
    await user.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(null));
  });

  it("pick multiple: отмеченные индексы", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-pick-many"));
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes[1]).toBeChecked(); // defaultSelected
    await user.click(boxes[0]);
    await user.click(boxes[2]);
    await user.click(screen.getByRole("button", { name: "OK" }));
    // Порядок — как у Set: defaultSelected (1) первым, затем клики.
    await waitFor(() => expect(res).toHaveBeenLastCalledWith([1, 0, 2]));
  });

  it("использует текущую локаль для default labels", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await changeLanguage("en");
    await user.click(screen.getByText("b-confirm"));
    expect(screen.getByRole("button", { name: "Yes" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await changeLanguage("ru");
    await user.click(screen.getByText("b-confirm"));
    expect(screen.getByRole("button", { name: "Да" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
  });

  it("перерисовывает descriptor title и actions открытого диалога при смене локали", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-open-localized"));
    expect(screen.getByRole("heading", { name: "Подтверждение" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отмена" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Да" })).toBeInTheDocument();

    await changeLanguage("en");

    expect(screen.getByRole("heading", { name: "Confirmation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes" })).toBeInTheDocument();
    expect(screen.getByText("localized-body")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith(true));
    await changeLanguage("ru");
  });

  it("перерисовывает confirm descriptor при смене локали", async () => {
    const user = userEvent.setup();
    render(<DialogProvider><Harness onResult={vi.fn()} /></DialogProvider>);

    await changeLanguage("ru");
    await user.click(screen.getByText("b-confirm-descriptor"));
    expect(screen.getAllByText("Подтверждение")).toHaveLength(2);

    await changeLanguage("en");
    expect(screen.getAllByText("Confirmation")).toHaveLength(2);
    await user.keyboard("{Escape}");
  });

  it("перерисовывает info descriptors при смене локали", async () => {
    const user = userEvent.setup();
    render(<DialogProvider><Harness onResult={vi.fn()} /></DialogProvider>);

    await changeLanguage("ru");
    await user.click(screen.getByText("b-info-descriptor"));
    expect(screen.getByRole("heading", { name: "Подтверждение" })).toBeInTheDocument();
    expect(screen.getByText("Да")).toBeInTheDocument();

    await changeLanguage("en");
    expect(screen.getByRole("heading", { name: "Confirmation" })).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    await user.keyboard("{Escape}");
  });

  it("open: async onClick → false оставляет модалку открытой", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-open-stay"));
    await user.click(screen.getByRole("button", { name: "Сейв" }));
    await waitFor(() => expect(screen.getByText("custom-body")).toBeInTheDocument());
    // Кнопка вернулась в рабочее состояние после async-обработчика.
    await waitFor(() => expect(screen.getByRole("button", { name: "Сейв" })).toBeEnabled());
    expect(res).not.toHaveBeenCalled();
  });

  it("open: onClick без false закрывает модалку со значением результата", async () => {
    const user = userEvent.setup();
    const res = vi.fn();
    render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

    await user.click(screen.getByText("b-open-close"));
    await user.click(screen.getByRole("button", { name: "Сейв" }));
    await waitFor(() => expect(res).toHaveBeenLastCalledWith("saved"));
    expect(screen.queryByText("custom-body-2")).not.toBeInTheDocument();
  });

  /* Легаси-обёртка #modal-root.open: fixed/затемнение/центрирование даёт
     CSS по id+классу — портал обязан рендериться внутрь этого контейнера. */
  describe("обёртка #modal-root.open", () => {
    function rootEl(): HTMLElement | null {
      return document.getElementById("modal-root");
    }

    it("открытая модалка лежит в #modal-root.open вместе с затемнением", async () => {
      const user = userEvent.setup();
      const res = vi.fn();
      render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

      const root = rootEl();
      expect(root).not.toBeNull();
      expect(root).not.toHaveClass("open");

      await user.click(screen.getByText("b-confirm"));
      expect(rootEl()).toHaveClass("open");
      const dlg = screen.getByRole("dialog");
      // Модалка и бекдроп — внутри обёртки (геометрия из styles.css:
      // #modal-root.open — fixed, flex-центрирование; .modal-backdrop — затемнение).
      expect(rootEl()!.contains(dlg)).toBe(true);
      const backdrop = rootEl()!.querySelector(".modal-backdrop");
      expect(backdrop).not.toBeNull();
      expect(rootEl()!.contains(backdrop!)).toBe(true);

      await user.click(within(dlg).getByRole("button", { name: "Да" }));
      await waitFor(() => expect(res).toHaveBeenLastCalledWith(true));
      expect(rootEl()).not.toHaveClass("open");
    });

    it("клик по фону (backdrop) закрывает модалку", async () => {
      const user = userEvent.setup();
      const res = vi.fn();
      render(<DialogProvider><Harness onResult={res} /></DialogProvider>);

      await user.click(screen.getByText("b-confirm"));
      const backdrop = document.querySelector("#modal-root .modal-backdrop")!;
      expect(backdrop).not.toBeNull();
      await user.click(backdrop as HTMLElement);
      await waitFor(() => expect(res).toHaveBeenLastCalledWith(false));
      expect(rootEl()).not.toHaveClass("open");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});

describe("KeymapDialog", () => {
  it("возвращает фокус на trigger и закрывается по Escape", async () => {
    const user = userEvent.setup();
    const trigger = document.createElement("button");
    trigger.textContent = "Открыть горячие клавиши";
    document.body.appendChild(trigger);
    trigger.focus();
    useOverlays.setState({ keymapOpen: true });
    render(<KeymapDialog />);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Закрыть" })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    trigger.remove();
    useOverlays.setState({ keymapOpen: false });
  });

  it("не выпускает Tab за пределы диалога", async () => {
    const user = userEvent.setup();
    useOverlays.setState({ keymapOpen: true });
    render(<KeymapDialog />);
    const close = await screen.findByRole("button", { name: "Закрыть" });
    close.focus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Закрыть" })).toHaveFocus();
    useOverlays.setState({ keymapOpen: false });
  });
});
