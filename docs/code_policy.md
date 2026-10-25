# 📜 Política de Codi, Estàndards i Seguretat

## 1. Nomenclatura i Estil (PEP 8 & Clean Code)
- **Variables i funcions**: `snake_case` (ex: `generate_reset_token`).
- **Classes**: `PascalCase` (ex: `UserAuthenticationManager`).
- **Constants**: `UPPER_SNAKE_CASE` (ex: `TOKEN_EXPIRATION_MINUTES = 15`).
- **Noms descriptius**: Evitar abreviatures ambigües (ex: utilitzar `user_email` en lloc de `u_e`).
- **Formatat i Linting**: El codi ha de complir les regles de `ruff` (límit recomanat de 100 caràcters per línia, importacions ordenades segons `isort`).

## 2. Estructura, Tipat i Documentació
- **Docstrings (Google Style - PEP 257)**: Tot mòdul, classe i funció o mètode ha d'incloure docstrings en format **Google Style** amb les seccions `Args:`, `Returns:` i `Raises:` quan escaigui.
- **Tipat estàtic (Type Hints - PEP 484)**: Totes les signatures de funcions i mètodes han d'incloure anotacions de tipus explícites d'entrada i sortida verificables amb `mypy` (ex: `def get_user(user_id: int) -> dict[str, Any]:`).
- **Mida de funcions i SRP**: Les funcions no han de superar les 30-40 línies de codi i han de seguir estrictament el Principi de Responsabilitat Única (SRP).
- **Injecció de dependències**: Els agents i controladors han de permetre la injecció opcional de serveis (`llm_service`, `github_service`) per facilitar el *mocking* en tests unitaris sense dependre d'efectes secundaris en temps d'importació.

## 3. Rendiment (Performance)
- **Complexitat temporal**: Evitar bucles anidats innecessaris ($O(n^2)$) sobre col·leccions grans.
- **Gestió de memòria**: Utilitzar generadors (`yield`) per a processament de grans volums de dades i mecanismes de purga amortitzada en estructures en memòria.
- **Consultes / I/O**: Minimitzar crides repetides a APIs o bases de dades dins de bucles.

## 4. Seguretat (OWASP Top 10)
- **A01: Broken Access Control**: Verificar permisos abans d'executar accions sobre recursos.
- **A02: Cryptographic Failures**: Utilitzar algoritmes d'encriptació/hashing segurs (ex: `scrypt`, `HMAC-SHA256`, `secrets` en lloc de `md5` o `random`).
- **A03: Injection (SQL/Command)**: Utilitzar consultes parametritzades i execució de subprocessos sense `shell=True` (llistes d'arguments); mai concatenar cadenes no confiables en comandes de sistema o SQL.
- **A04: Insecure Design**: Validar entrades de l'usuari rigorosament (`pydantic` o expressions regulars acotades).
- **A05: Security Misconfiguration & Secret Isolation**: No exposar traces d'error o dades sensibles a les respostes ni filtrar credencials (`GITHUB_TOKEN`, `GEMINI_API_KEY`) a l'entorn de subprocessos de test.
- **A07: Identification & Authentication Failures**: Fluxos de recuperació de contrasenya sense revelar l'existència d'usuaris, amb comparació en temps constant (`hmac.compare_digest`), consum atòmic contra TOCTOU i tokens d'un sol ús amb expiració breu.

## 5. Disseny de Proves i Aïllament (PyTest Best Practices)
- **Aïllament d'I/O (`tmp_path`)**: Els tests que generen fitxers o logs han d'utilitzar sempre la fixture `tmp_path` de `pytest` i mai escriure en directoris d'execució o producció.
- **Eficiència en límits i rotació**: Per provar comportaments com la rotació de fitxers, limitar el paràmetre de mida (`max_bytes=500` o `1024`) per validar-lo en mil·lisegons, evitant escriure grans volums de dades en bucles lents.
- **Canvis Mínims en Components Existents**: Modificar exclusivament les línies necessàries en fitxers existents per incorporar noves funcionalitats, preservant totes les signatures i implementacions prèvies.
