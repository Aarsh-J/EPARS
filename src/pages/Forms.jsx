import "./Forms.css";
import { FORM_GROUPS } from "../data/groupForms.js";

function FormCard({ form }) {
  const ready = Boolean(form.url);

  return (
    <div className={`module-card form-card ${ready ? "active" : "disabled"}`}>
      <div className="form-card-top">
        <span className="form-code">{form.code}</span>
        <span className="form-who">{form.who}</span>
      </div>
      <div className="module-info">
        <h3>{form.title}</h3>
        <p>{form.description}</p>
      </div>
      {ready ? (
        <a
          className="btn-analyse form-open-btn"
          href={form.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open form ↗
        </a>
      ) : (
        <span className="form-unavailable">Link not added yet</span>
      )}
    </div>
  );
}

export default function Forms() {
  return (
    <>
      <div className="dashboard-intro">
        <p>
          Use these forms to record progress, reviews and feedback. Each form opens in a
          new tab, and your answers are saved to EPARS automatically when you submit.
        </p>
      </div>

      {FORM_GROUPS.map((group) => (
        <section className="forms-group" key={group.id}>
          <h2 className="forms-group-title">{group.title}</h2>
          <p className="forms-group-desc">{group.description}</p>
          <div className="module-grid">
            {group.forms.map((form) => (
              <FormCard form={form} key={form.code} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}