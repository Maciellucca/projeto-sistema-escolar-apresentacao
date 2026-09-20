/*
 * Busca ao vivo de aluno na tela inicial — ao escolher um resultado,
 * navega direto pra página do aluno.
 */
document.addEventListener("DOMContentLoaded", () => {
  const campo = document.getElementById("busca-aluno-dashboard");
  if (!campo) return;

  const resultados = document.getElementById("resultados-busca-aluno-dashboard");
  let temporizador;

  campo.addEventListener("input", () => {
    clearTimeout(temporizador);
    const termo = campo.value.trim();
    if (termo.length < 2) {
      resultados.innerHTML = "";
      resultados.hidden = true;
      return;
    }
    temporizador = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/alunos?q=${encodeURIComponent(termo)}`);
        const alunos = await resp.json();
        resultados.innerHTML = "";
        if (alunos.length === 0) {
          const vazio = document.createElement("div");
          vazio.className = "resultado-busca-trocar muted";
          vazio.textContent = "Nenhum aluno encontrado.";
          resultados.appendChild(vazio);
          resultados.hidden = false;
          return;
        }
        alunos.forEach((a) => {
          const item = document.createElement("div");
          item.className = "resultado-busca-trocar";
          item.textContent = `${a.nome} (${a.turma})`;
          item.addEventListener("click", () => {
            window.location.href = `/aluno/${a.id}`;
          });
          resultados.appendChild(item);
        });
        resultados.hidden = false;
      } catch (err) {
        resultados.hidden = true;
      }
    }, 250);
  });

  document.addEventListener("click", (ev) => {
    if (!campo.contains(ev.target) && !resultados.contains(ev.target)) {
      resultados.hidden = true;
    }
  });
});
