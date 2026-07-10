import { Navigate, createBrowserRouter } from "react-router-dom";
import App from "../App";
import { CharacterizationPage } from "../pages/CharacterizationPage";
import { DashboardPage } from "../pages/DashboardPage";
import { ProcessingPage } from "../pages/ProcessingPage";
import { ProcessRecordPage } from "../pages/ProcessRecordPage";
import { RawDataPage } from "../pages/RawDataPage";
import { SampleMaintenancePage } from "../pages/SampleMaintenancePage";
import { SamplesPage } from "../pages/SamplesPage";
import { TestDataPage } from "../pages/TestDataPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: "samples",
        element: <SamplesPage />,
      },
      {
        path: "samples/maintenance",
        element: <SampleMaintenancePage />,
      },
      {
        path: "raw-data",
        element: <RawDataPage />,
      },
      {
        path: "characterization",
        element: <CharacterizationPage />,
      },
      {
        path: "test-data",
        element: <TestDataPage />,
      },
      {
        // Spec 004 Phase 2b: performance folds into Artifacts — legacy routes
        // redirect into the unified Raw Data / Artifacts list, filtered to type.
        path: "performance-datasets",
        element: <Navigate to="/raw-data?data_type=performance" replace />,
      },
      {
        path: "data",
        element: <TestDataPage />,
      },
      {
        path: "performance",
        element: <Navigate to="/raw-data?data_type=performance" replace />,
      },
      {
        path: "processing",
        element: <ProcessingPage />,
      },
      {
        path: "process-records",
        element: <ProcessRecordPage />,
      },
    ],
  },
]);
