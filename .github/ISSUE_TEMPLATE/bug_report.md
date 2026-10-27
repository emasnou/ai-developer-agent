---
name: "🐛 Informe d'Error o Incidència de Seguretat (Bug Report)"
about: "Reporta un error funcional, regressió de tests o vulnerabilitat OWASP"
title: "fix: "
labels: ["bug", "triage"]
assignees: []
---

## 🐛 Descripció de l'Error
[Descripció clara i concisa de l'error o comportament inesperat]

## 🔄 Passos per Reproduir (Format BDD)
- **Given (Donat):** [Configuració, repositori actiu o estat inicial]
- **When (Quan):** [Comanda executada o entrada proporcionada]
- **Then (Aleshores — Resultat actual):** [Excepció, traça d'error o comportament erroni observat]
- **Expected (Resultat esperat):** [Comportament correcte segons l'especificació]

## 🛡️ Impacte de Seguretat (OWASP Top 10)
- **Afecta la seguretat?** [Sí / No — En cas afirmatiu, indicar la categoria OWASP (ex: A01 Path Traversal, A03 Injection, A07 Auth)]

## 🧪 Test de Regressió Requerit
- [ ] Crear test unitari a `tests/unit/` que reprodueixi la fallada abans d'aplicar la correcció.

