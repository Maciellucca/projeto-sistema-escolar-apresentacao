document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    el.addEventListener("click", () => el.remove());
    el.title = "Clique para dispensar";
    el.style.cursor = "pointer";
  });

  const botaoConta = document.getElementById("botao-conta");
  const menuConta = document.getElementById("menu-conta");
  if (botaoConta && menuConta) {
    const fechar = () => {
      menuConta.hidden = true;
      botaoConta.setAttribute("aria-expanded", "false");
    };
    const abrir = () => {
      menuConta.hidden = false;
      botaoConta.setAttribute("aria-expanded", "true");
    };
    botaoConta.addEventListener("click", (e) => {
      e.stopPropagation();
      menuConta.hidden ? abrir() : fechar();
    });
    document.addEventListener("click", (e) => {
      if (!menuConta.hidden && !menuConta.contains(e.target)) fechar();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") fechar();
    });
  }

  // Abas genéricas: qualquer [data-tab-btn]/[data-tab-panel] dentro do
  // [data-tabs] mais próximo. Funciona com grupos aninhados (ex: abas da
  // ficha do aluno, com um seletor de bimestre aninhado dentro de uma delas).
  document.querySelectorAll("[data-tab-btn]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const grupo = botao.closest("[data-tabs]");
      if (!grupo) return;
      const alvo = botao.dataset.tabBtn;
      const doGrupo = (seletor) =>
        [...grupo.querySelectorAll(seletor)].filter((el) => el.closest("[data-tabs]") === grupo);

      doGrupo("[data-tab-btn]").forEach((b) => {
        const ativo = b === botao;
        b.classList.toggle("ativa", ativo);
        b.setAttribute("aria-selected", ativo ? "true" : "false");
      });
      doGrupo("[data-tab-panel]").forEach((painel) => {
        painel.hidden = painel.dataset.tabPanel !== alvo;
      });
    });
  });
});
