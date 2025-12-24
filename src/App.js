import React, { useState } from "react";

/**
 * Application simple avec 3 onglets:
 * - Vente
 * - Maintenance
 * - Caméra de surveillance
 *
 * Chaque onglet affiche un gros bouton d'action.
 */

const TABS = [
  { id: "vente", label: "Vente" },
  { id: "maintenance", label: "Maintenance" },
  { id: "camera", label: "Caméra de surveillance" },
];

export default function App() {
  const [active, setActive] = useState("vente");

  function handleAction(tabId) {
    switch (tabId) {
      case "vente":
        // TODO: remplacer par votre logique réelle (ex: ouvrir formulaire de vente)
        alert("Action Vente: ouvrir l'écran de saisie d'une nouvelle vente.");
        break;
      case "maintenance":
        alert("Action Maintenance: ouvrir le tableau de bord de maintenance.");
        break;
      case "camera":
        // Exemple: ouvrir une URL de caméra (remplacez par votre flux)
        // window.open("http://IP_DE_LA_CAMERA:PORT", "_blank");
        alert("Action Caméra: pas de caméra configurée. Remplacez par votre flux.");
        break;
      default:
        break;
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="title">Mon Application</h1>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab-btn ${active === t.id ? "active" : ""}`}
              onClick={() => setActive(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="content">
        <section className="panel">
          <h2 className="panel-title">
            {TABS.find((x) => x.id === active)?.label}
          </h2>

          <p className="panel-desc">
            {active === "vente" &&
              "Créer une nouvelle vente, rechercher produits/clients et finaliser."}
            {active === "maintenance" &&
              "Accéder aux tâches de maintenance, tickets et historique."}
            {active === "camera" &&
              "Afficher le flux de la caméra de surveillance (configurable)."}
          </p>

          <button
            className="action-button"
            onClick={() => handleAction(active)}
          >
            {active === "vente" && "Nouvelle vente"}
            {active === "maintenance" && "Ouvrir maintenance"}
            {active === "camera" && "Voir la caméra"}
          </button>
        </section>
      </main>

      <footer className="footer">© 2025 — Votre société</footer>
    </div>
  );
}