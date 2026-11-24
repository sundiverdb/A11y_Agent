# A11y Agent

[English](README.md) | **Français**

A11y Agent audite des pages web avec axe-core, WAVE et Lighthouse. Il s'utilise depuis une interface dans le navigateur (`a11yagent.html`) ou comme serveur MCP pour Claude et d'autres clients MCP. L'interface et les rapports sont en anglais.

Les outils automatiques ne détectent qu'une partie des problèmes WCAG. Un résultat sans erreur ne prouve pas la conformité, et ces outils ne testent pas les menus, les boîtes de dialogue ni les tunnels de commande.

## Installer le serveur MCP

Nécessite Python 3.11 ou une version plus récente.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
cp .env.example a11y_agent.env   # puis ajoutez votre clé WAVE
```

Lighthouse est facultatif : `npm install -g lighthouse`.

Ajoutez ce bloc aux réglages de votre client MCP. Dans l'application de bureau Claude, ce fichier s'appelle `claude_desktop_config.json`. Utilisez des chemins absolus, puis redémarrez l'application.

```json
{
  "mcpServers": {
    "a11y-agent": {
      "command": "/absolute/path/to/A11y_Agent/.venv/bin/python",
      "args": ["/absolute/path/to/A11y_Agent/mcp_server.py"]
    }
  }
}
```

## Outils

| Outil | Ce qu'il fait |
|---|---|
| `audit_url` | Audite une page |
| `start_batch_audit` | Lance un audit en arrière-plan à partir d'une liste d'URL ou d'un `sitemap_url` |
| `get_batch_status` | Affiche l'avancement |
| `get_batch_report` | Résume les résultats et écrit `pages.csv` et `issues.csv` |
| `stop_batch_audit` | S'arrête après la page en cours |
| `resume_batch_audit` | Reprend un audit en sautant les pages déjà enregistrées |
| `list_batch_audits` | Liste les audits enregistrés |
| `check_wave_credits` | Affiche le solde de crédits WAVE enregistré lors de la dernière requête WAVE (gratuit) ; avec `live=True`, une petite requête WAVE payante le met à jour |
| `list_access_topics` | Liste les thèmes (access topics) de l'Accessibility Considerations Toolkit de Microsoft |
| `get_access_consideration` | Renvoie la liste de contrôle d'un thème, ses modèles de technologies d'assistance et ses stratégies de test, avec les garde-fous obligatoires |
| `get_evaluation_guide` | Renvoie un document de méthodologie ou d'heuristiques, comme l'échelle de gravité |
| `get_wcag_criterion` | Renvoie le texte d'un critère de succès des WCAG 2.2, pour annoter les résultats |

Les résultats sont enregistrés dans `~/.a11y_agent/runs/<run_id>/`. Importez les fichiers CSV dans Google Sheets ou Excel.

## Accessibility Considerations Toolkit

Les quatre outils du toolkit couvrent ce qu'axe, WAVE et Lighthouse ne savent pas vérifier : les tests au clavier, au lecteur d'écran, au zoom et à la commande vocale, ainsi que les tests cognitifs, classés selon la norme EN 301 549. Ils lisent une copie figée du
[toolkit de Microsoft](https://github.com/microsoft/Microsoft-Accessibility/tree/main/Accessibility-Considerations-Toolkit)
dans `vendor/ms-act/`. Ils fonctionnent donc hors ligne et ne changent pas tant que vous ne mettez pas cette copie à jour.
Consultez `vendor/ms-act/VENDORED.md` pour le commit utilisé, les licences et la procédure de mise à jour.

## Utiliser la page dans le navigateur

1. Double-cliquez sur `Start A11y Agent.command` dans le Finder. Il démarre le serveur local et ouvre
   `a11yagent.html`. Fermez sa fenêtre Terminal pour arrêter le serveur. (Vous pouvez aussi lancer
   `.venv/bin/python audit_server.py` et ouvrir la page vous-même.)
2. Choisissez **One page** (une page) et saisissez l'adresse d'une page, ou **A whole site** (un site entier) et saisissez
   son sitemap (souvent `/sitemap.xml` ; WordPress utilise `/wp-sitemap.xml`, ou `/sitemap_index.xml` avec Yoast SEO).
3. Pour un site entier, choisissez où WAVE et Lighthouse s'exécutent. **One page of each type** (une page de chaque type)
   limite la consommation de crédits WAVE ; axe vérifie quand même chaque page.

Les audits de site utilisent le même moteur que les outils d'audit par lots du serveur MCP. Les résultats sont enregistrés
dans `~/.a11y_agent/runs/`, la page affiche l'avancement et un résumé, et **Stop audit** (arrêter l'audit) met fin à
l'audit après la page en cours.

## Fonctionnement des audits par lots

- **Rythme :** une page à la fois, avec un délai de 2 secondes par défaut.
- **Crédits WAVE :** WAVE et Lighthouse s'exécutent sur la première page de chaque gabarit. Réglez `sampled_tools_per_template` sur 0 pour les lancer sur chaque page. Le résultat du lancement indique le nombre de requêtes prévu.
- **Blocages :** une page qui renvoie 403, 429 ou 503 est retentée une fois après 60 secondes. Cinq pages bloquées d'affilée mettent l'audit en pause.
- **Regroupement :** `issues.csv` liste chaque règle une seule fois, avec le nombre de pages touchées et les gabarits concernés. Les noms de gabarits sont déduits des chemins d'URL.

## Tests

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

## Licence

A11y Agent est publié sous [licence MIT](LICENSE) (texte en anglais). Chacun peut le forker, l'utiliser et l'adapter,
y compris dans un cadre commercial, à condition de conserver la mention de copyright et la licence avec le code.

Le Microsoft Accessibility Considerations Toolkit inclus dans `vendor/ms-act/` garde sa propre licence :
MIT de Microsoft, plus les conditions de la licence de document du W3C pour les contenus WCAG et d'accessibilité
cognitive qu'il adapte. Consultez `vendor/ms-act/VENDORED.md` pour plus de détails.
