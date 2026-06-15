import { createBrowserRouter } from "react-router-dom";
import App from "../App";
import { CharacterizationPage } from "../pages/CharacterizationPage";
import { DashboardPage } from "../pages/DashboardPage";
import { PerformanceDatasetPage } from "../pages/PerformanceDatasetPage";
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
        path: "performance-datasets",
        element: <PerformanceDatasetPage />,
      },
      {
        path: "data",
        element: <TestDataPage />,
      },
      {
        path: "performance",
        element: <PerformanceDatasetPage />,
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
