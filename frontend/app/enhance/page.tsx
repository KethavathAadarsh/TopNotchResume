import { Suspense } from "react";
import EnhanceClient from "./EnhanceClient";

export default function EnhancePage() {
  return (
    <Suspense fallback={null}>
      <EnhanceClient />
    </Suspense>
  );
}
