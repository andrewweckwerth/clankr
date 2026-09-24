import { PIPELINE_STAGES } from '@/lib/pipeline';

export default function PipelineOverview() {
  return (
    <ol className="pipeline-stages" aria-label="Pipeline stages">
      {PIPELINE_STAGES.map((stage, index) => (
        <li key={stage.key}>
          <p className="stage-number">0{index + 1} · {stage.service}</p>
          <p className="stage-name">{stage.name}</p>
          <p className="stage-description">{stage.description}</p>
        </li>
      ))}
    </ol>
  );
}
