import { CalculateMetadataFunction, Composition } from "remotion";
import { DemoVideo } from "./DemoVideo";
import { FPS, buildTimeline } from "./timeline";

type Props = Record<string, unknown>;

// Длительность считается из записанного диалога: поменяли сценарий — ролик подстроился сам
const calculateMetadata: CalculateMetadataFunction<Props> = () => ({
  durationInFrames: buildTimeline().duration,
});

export const MyComposition = () => (
  <Composition
    id="BotDemo"
    component={DemoVideo}
    durationInFrames={FPS * 60}
    fps={FPS}
    width={1920}
    height={1080}
    defaultProps={{}}
    calculateMetadata={calculateMetadata}
  />
);
