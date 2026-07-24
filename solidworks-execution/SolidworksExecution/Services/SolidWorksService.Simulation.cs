using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidworksExecution.Models;
using CosWorks = SolidWorks.Interop.cosworks;

namespace SolidworksExecution.Services
{
    // SolidWorks Simulation (cosworks) tools: static FEA + topology studies.
    // COM surface verified by reflection over SolidWorks.Interop.cosworks.dll and a live
    // Python prototype (2026-07). All entity arrays marshal as object[] (SAFEARRAY of
    // VARIANT-wrapped dispatches). Enum ints below are from the interop enums — do not guess.
    public partial class SolidWorksService
    {
        private const string SimulationDllPath =
            @"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\Simulation\cosworks.dll";

        // swsAnalysisStudyType_e
        private const int SimStudyStatic = 0;
        private const int SimStudyTopology = 13;   // swsAnalysisStudyTypeTopology_Static
        // swsRestraintType_e
        private const int SimRestraintFixed = 0;
        // swsForceType_e / swsForceUnit_e
        private const int SimForceNormal = 1;
        private const int SimForceUnitNewton = 0;
        private const int SimSelectionFaceEdgeVertexPoint = 0;
        // swsMeshQuality_e
        private const int SimMeshDraft = 0;
        private const int SimMeshHigh = 1;
        private const int SimLinearUnitMeters = 2;
        // swsStressComponent_e
        private const int SimStressVonMises = 9;
        private const int SimDisplacementResultant = 3;
        private const int SimStaticStep = 1;
        private const int SimStrengthUnitPascal = 0;
        private const int SimFosCriterionVonMises = 0;
        private const int SimFosCriterionAutomatic = 4;
        private const int SimFosShellTopFace = 1;
        private const int SimFosStressLimitUserDefined = 2;
        // swsTopologyStudyGoalType_e
        private const int SimTopoGoalStiffness = 0;
        private const int SimTopoGoalMinMass = 2;
        // swsTopologyStudyMassConstraintOption_e
        private const int SimTopoMassPercent = 1;

        // ---- plumbing -------------------------------------------------------------

        private dynamic GetCosmosWorks(out string error)
        {
            error = null;
            try
            {
                dynamic cb = _solidWorks.GetAddInObject("SldWorks.Simulation");
                if (cb == null)
                {
                    int rc = _solidWorks.LoadAddIn(SimulationDllPath);
                    if (rc != 0 && rc != 2) // 0 loaded, 2 already loaded
                    {
                        error = $"Simulation add-in failed to load (rc={rc}). Is SOLIDWORKS Simulation installed at {SimulationDllPath}?";
                        return null;
                    }
                    cb = _solidWorks.GetAddInObject("SldWorks.Simulation");
                }
                if (cb == null)
                {
                    error = "Simulation add-in object unavailable after load.";
                    return null;
                }
                dynamic cos = cb.CosmosWorks;
                if (cos == null) error = "CosmosWorks root object is null.";
                return cos;
            }
            catch (COMException ex)
            {
                error = "COM error acquiring Simulation add-in: " + ex.Message;
                return null;
            }
        }

        private dynamic FindSimStudy(dynamic studyMgr, string name, out int index)
        {
            index = -1;
            int count = studyMgr.StudyCount;
            for (int i = 0; i < count; i++)
            {
                dynamic s = studyMgr.GetStudy(i);
                if (s != null && string.Equals((string)s.Name, name, StringComparison.OrdinalIgnoreCase))
                {
                    index = i;
                    return s;
                }
            }
            return null;
        }

        // Select faces by model-space coordinates (meters); returns dispatches for entity params.
        private object[] PickSimFaces(IModelDoc2 modelDoc, JArray faceCoords, out string error)
        {
            error = null;
            var faces = new List<object>();
            var selMgr = (ISelectionMgr)modelDoc.SelectionManager;
            foreach (var t in faceCoords)
            {
                double fx = t.Value<double>("x"), fy = t.Value<double>("y"), fz = t.Value<double>("z");
                modelDoc.ClearSelection2(true);
                bool ok = modelDoc.Extension.SelectByID2("", "FACE", fx, fy, fz, false, 0, null, 0);
                if (!ok)
                {
                    error = $"No face found at ({fx}, {fy}, {fz}). Coordinates are model-space METERS on the face surface.";
                    return null;
                }
                object face = selMgr.GetSelectedObject6(1, -1);
                if (face == null)
                {
                    error = $"Face selection at ({fx}, {fy}, {fz}) returned no object.";
                    return null;
                }
                // Simulation expects SAFEARRAY elements explicitly marshaled as VT_DISPATCH.
                // Plain RCWs fail AddRestraint/AddForce2 on SolidWorks 2026.
                faces.Add(new DispatchWrapper(face));
            }
            modelDoc.ClearSelection2(true);
            if (faces.Count == 0) error = "faces array is empty — supply at least one {x,y,z}.";
            return faces.Count > 0 ? faces.ToArray() : null;
        }

        private ExecutionResponse SimGuardEntry(ToolRequest request, bool mutating, out IModelDoc2 modelDoc,
            out dynamic studyMgr)
        {
            modelDoc = null;
            studyMgr = null;

            if (mutating && _guard.IsDuplicate(request.OperationId))
                return _guard.GetDuplicate(request.OperationId);

            if (mutating && !_guard.IsStateVersionValid(request.StateVersion))
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                    "INVALID_STATE_VERSION", "Incoming state_version does not match current state.");

            if (!EnsureConnected())
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                    "COM_ATTACH_FAILED", "SolidWorks process not found or COM not registered.");

            modelDoc = _solidWorks.IActiveDoc2 as IModelDoc2;
            if (modelDoc == null)
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                    "NO_ACTIVE_DOCUMENT", "No active document found in SolidWorks.");

            string simError;
            dynamic cos = GetCosmosWorks(out simError);
            if (cos == null)
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                    "SIMULATION_UNAVAILABLE", simError);

            dynamic adoc = cos.ActiveDoc;
            if (adoc == null)
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                    "SIMULATION_NO_DOC", "Simulation has no active document (open a part or assembly).");

            studyMgr = adoc.StudyManager;
            return null; // no error — caller proceeds
        }

        private ExecutionResponse SimOk(ToolRequest request, IModelDoc2 modelDoc, bool mutating,
            List<string> features, object resultGeometry)
        {
            int sv = _guard.GetCurrentStateVersion() + (mutating ? 1 : 0);
            var response = new ExecutionResponse
            {
                OperationId = request.OperationId,
                Status = "COMPLETED",
                Verified = true,
                StateVersion = sv,
                CadState = new CadState
                {
                    StateVersion = sv,
                    ActiveDocument = modelDoc.GetTitle(),
                    DocumentType = DocTypeName(modelDoc),
                    ActiveSketch = null,
                    Features = features ?? new List<string>(),
                    Dimensions = new List<string>()
                },
                ResultGeometry = resultGeometry,
                Error = null
            };
            if (mutating) _guard.RegisterCompleted(request.OperationId, response);
            return response;
        }

        private static Dictionary<string, object> NodeMinMaxSummary(object raw)
        {
            var summary = new Dictionary<string, object>();
            if (raw is Array arr)
            {
                summary["raw"] = arr.Cast<object>().ToList();
                // Documented order: {min node, min value, max node, max value}.
                if (arr.Length >= 4)
                {
                    summary["min_node"] = Convert.ToInt32(arr.GetValue(0));
                    summary["min"] = Convert.ToDouble(arr.GetValue(1));
                    summary["max_node"] = Convert.ToInt32(arr.GetValue(2));
                    summary["max"] = Convert.ToDouble(arr.GetValue(3));
                }
            }
            else summary["raw"] = raw;
            return summary;
        }

        private static Dictionary<string, object> PairMinMaxSummary(object raw)
        {
            var summary = new Dictionary<string, object>();
            if (raw is Array arr)
            {
                summary["raw"] = arr.Cast<object>().ToList();
                if (arr.Length >= 2)
                {
                    summary["min"] = Convert.ToDouble(arr.GetValue(0));
                    summary["max"] = Convert.ToDouble(arr.GetValue(1));
                }
            }
            else summary["raw"] = raw;
            return summary;
        }

        // ---- tools ----------------------------------------------------------------

        public ExecutionResponse SimCreateStudy(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string name = p?.Value<string>("name");
                string type = p?.Value<string>("study_type") ?? "static";
                if (string.IsNullOrEmpty(name))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "name is required. Letters/digits/underscores only — '?' etc. are rejected by Simulation.");

                if (!Regex.IsMatch(name, @"^[A-Za-z0-9_]+$"))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "name may contain letters, digits, and underscores only.");

                if (type != "static" && type != "topology")
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "study_type must be 'static' or 'topology'.");

                int studyType = type == "topology" ? SimStudyTopology : SimStudyStatic;

                int existingIdx;
                if (FindSimStudy(sm, name, out existingIdx) != null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_EXISTS", $"A study named '{name}' already exists. Delete it first or pick another name.");

                int err = 0;
                dynamic study = sm.CreateNewStudy3(name, studyType, 0, ref err);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_CREATE_FAILED",
                        $"CreateNewStudy3 err={err} (2=duplicate/invalid name, 3=type not defined). Type was {studyType}.");

                int idx;
                FindSimStudy(sm, name, out idx);
                if (idx >= 0) sm.ActiveStudy = idx;

                return SimOk(request, modelDoc, true,
                    new List<string> { $"study={name}", $"type={type}", $"index={idx}" },
                    new { study = name, type, index = idx });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimAddFixture(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("study_name");
                var faceCoords = p?.Value<JArray>("faces");
                if (string.IsNullOrEmpty(studyName) || faceCoords == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "study_name and faces [{x,y,z}...] (model-space meters) are required.");

                int idx;
                dynamic study = FindSimStudy(sm, studyName, out idx);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");
                sm.ActiveStudy = idx;

                string faceErr;
                object[] faces = PickSimFaces(modelDoc, faceCoords, out faceErr);
                if (faces == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "FACE_PICK_FAILED", faceErr);

                var lr = (CosWorks.ICWLoadsAndRestraintsManager)study.LoadsAndRestraintsManager;
                int err = 0;
                CosWorks.CWRestraint restraint = lr.AddRestraint(
                    SimRestraintFixed, (object)faces, null, out err);
                if (restraint == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "RESTRAINT_FAILED", $"AddRestraint err={err} (swsRestraintError_e).");

                return SimOk(request, modelDoc, true,
                    new List<string> { $"study={studyName}", $"fixture=fixed", $"faces={faces.Length}" },
                    new { study = studyName, fixture = "fixed", face_count = faces.Length, lbc_count = (int)lr.Count });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimAddForce(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("study_name");
                var faceCoords = p?.Value<JArray>("faces");
                double? newtons = p?.Value<double?>("newtons");
                if (string.IsNullOrEmpty(studyName) || faceCoords == null || newtons == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "study_name, faces [{x,y,z}...], and newtons are required.");

                int idx;
                dynamic study = FindSimStudy(sm, studyName, out idx);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");
                sm.ActiveStudy = idx;

                string faceErr;
                object[] faces = PickSimFaces(modelDoc, faceCoords, out faceErr);
                if (faces == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "FACE_PICK_FAILED", faceErr);

                var lr = (CosWorks.ICWLoadsAndRestraintsManager)study.LoadsAndRestraintsManager;
                int err = 0;
                CosWorks.CWForce force = lr.AddForce2(
                    SimForceNormal, SimSelectionFaceEdgeVertexPoint, (object)faces, null, out err);
                if (force == null)
                {
                    err = 0;
                    force = lr.AddForce(SimForceNormal, (object)faces, null, out err);
                }
                if (force == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "FORCE_FAILED", $"AddForce2/AddForce err={err} (swsForceError_e).");

                force.Unit = SimForceUnitNewton;
                force.NormalForceOrTorqueValue = newtons.Value;

                return SimOk(request, modelDoc, true,
                    new List<string> { $"study={studyName}", $"force={newtons}N normal", $"faces={faces.Length}" },
                    new { study = studyName, newtons = newtons.Value, face_count = faces.Length, lbc_count = (int)lr.Count });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimMeshAndRun(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("study_name");
                double elementSize = p?.Value<double?>("element_size") ?? 0.006;
                double tolerance = p?.Value<double?>("tolerance") ?? (elementSize / 20.0);
                bool draft = p?.Value<bool?>("draft_quality") ?? false;
                if (string.IsNullOrEmpty(studyName))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "study_name is required.");

                int idx;
                dynamic study = FindSimStudy(sm, studyName, out idx);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");
                sm.ActiveStudy = idx;

                // CreateMesh's first parameter is swsLinearUnit_e, not mesh quality.
                // Quality belongs on ICWMesh. Passing 0 here means millimeters and turns
                // 0.006 into a six-micron mesh, which can run indefinitely on this part.
                dynamic mesh = study.Mesh;
                mesh.Quality = draft ? SimMeshDraft : SimMeshHigh;
                int meshRc = study.CreateMesh(SimLinearUnitMeters, elementSize, tolerance);
                if (meshRc != 0)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MESH_FAILED", $"CreateMesh rc={meshRc} (swsStudyMeshError_e). element_size/tolerance are METERS.");

                int runRc = study.RunAnalysis();
                if (runRc != 0)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "RUN_FAILED", $"RunAnalysis rc={runRc} (swsRunAnalysisError_e). Check loads/fixtures are defined.");

                return SimOk(request, modelDoc, true,
                    new List<string> { $"study={studyName}", "meshed+solved" },
                    new { study = studyName, element_size = elementSize, solved = true });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimGetResults(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, false, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("study_name");
                if (string.IsNullOrEmpty(studyName))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "study_name is required.");

                int idx;
                dynamic study = FindSimStudy(sm, studyName, out idx);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");
                sm.ActiveStudy = idx;

                var results = (CosWorks.ICWResults)study.Results;
                if (results == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "NO_RESULTS", "Study has no results — run sim_mesh_and_run first.");

                double yieldStrengthPa = p?.Value<double?>("yield_strength_pa") ?? 0.0;
                if (yieldStrengthPa < 0 || double.IsNaN(yieldStrengthPa) || double.IsInfinity(yieldStrengthPa))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "yield_strength_pa must be a finite number >= 0.");

                var payload = new Dictionary<string, object>();
                int err = 0;
                double? maximumStressPa = null;

                try
                {
                    object vm = results.GetMinMaxStress(
                        SimStressVonMises, 0, SimStaticStep, null, SimStrengthUnitPascal, out err);
                    var stress = NodeMinMaxSummary(vm);
                    payload["von_mises_Pa"] = stress;
                    payload["von_mises_err"] = err;
                    if (err == 0 && stress.ContainsKey("max"))
                        maximumStressPa = Convert.ToDouble(stress["max"]);
                }
                catch (Exception e) { payload["von_mises_error"] = e.Message; }

                try
                {
                    err = 0;
                    object disp = results.GetMinMaxDisplacement(
                        SimDisplacementResultant, SimStaticStep, null, SimLinearUnitMeters, out err);
                    payload["displacement_m"] = NodeMinMaxSummary(disp);
                    payload["displacement_err"] = err;
                }
                catch (Exception e) { payload["displacement_error"] = e.Message; }

                try
                {
                    err = 0;
                    object fos;
                    string fosSource;
                    if (yieldStrengthPa > 0)
                    {
                        fos = results.GetMinMaxFactorOfSafetyWithDetailSettings2(
                            true, null, SimFosCriterionVonMises,
                            false, 0.0, SimStrengthUnitPascal,
                            SimFosStressLimitUserDefined, yieldStrengthPa,
                            SimFosStressLimitUserDefined, yieldStrengthPa,
                            1.0, 1.0, false, SimFosShellTopFace, 0, out err);
                        fosSource = "user_defined_yield_strength";
                    }
                    else
                    {
                        fos = results.GetMinMaxFactorOfSafety2(
                            true, null, SimFosCriterionAutomatic, SimFosShellTopFace, 0, out err);
                        fosSource = "material";
                    }

                    var fosSummary = PairMinMaxSummary(fos);
                    fosSummary["source"] = fosSource;
                    if (yieldStrengthPa > 0) fosSummary["yield_strength_pa"] = yieldStrengthPa;
                    if (err != 0 && yieldStrengthPa > 0 && maximumStressPa > 0)
                    {
                        fosSummary["min"] = yieldStrengthPa / maximumStressPa.Value;
                        fosSummary["source"] = "yield_strength_divided_by_max_von_mises";
                    }
                    payload["factor_of_safety"] = fosSummary;
                    payload["fos_err"] = err;
                }
                catch (Exception e) { payload["fos_error"] = e.Message; }

                return SimOk(request, modelDoc, false,
                    new List<string> { $"study={studyName}", "results-read" }, payload);
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimTopologySetup(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("study_name");
                string goal = p?.Value<string>("goal") ?? "best_stiffness";
                double massReduction = p?.Value<double?>("mass_reduction_percent") ?? 50.0;
                double minThickness = p?.Value<double?>("min_thickness") ?? 0.003;
                var preservedCoords = p?.Value<JArray>("preserved_faces");
                if (string.IsNullOrEmpty(studyName))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "study_name is required (must be a topology study).");

                int idx;
                dynamic study = FindSimStudy(sm, studyName, out idx);
                if (study == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");
                sm.ActiveStudy = idx;

                var topo = (CosWorks.ICWTopologyStudyManager)study.TopologyStudyManager;
                if (topo == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "NOT_TOPOLOGY_STUDY", $"'{studyName}' has no TopologyStudyManager — create it with study_type='topology'.");

                if (goal != "best_stiffness" && goal != "minimize_mass")
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "goal must be 'best_stiffness' or 'minimize_mass'.");
                if (massReduction <= 0 || massReduction >= 100 || double.IsNaN(massReduction))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "mass_reduction_percent must be greater than 0 and less than 100.");
                if (minThickness < 0 || double.IsNaN(minThickness) || double.IsInfinity(minThickness))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "INVALID_PARAMETER", "min_thickness must be a finite number >= 0 meters.");

                var applied = new List<string>();
                int goalType = goal == "minimize_mass" ? SimTopoGoalMinMass : SimTopoGoalStiffness;

                topo.BeginEdit();
                int goalRc = topo.CreateGoal(goalType);
                int goalManagerRc = topo.EndEdit();
                if (goalRc != 0 || goalManagerRc != 0)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "TOPOLOGY_GOAL_FAILED", $"CreateGoal rc={goalRc}; manager EndEdit rc={goalManagerRc}.");
                applied.Add($"goal={goal} rc=0");

                // Maximize stiffness creates a non-removable default "Mass Constraint 1".
                // Edit that constraint instead of creating a duplicate (manager error 7).
                if (goalType == SimTopoGoalStiffness)
                {
                    topo.BeginEdit();
                    int err;
                    CosWorks.CWTopologyMassConstraint mass = topo.GetMassConstraint("Mass Constraint 1", out err);
                    if (mass == null || err != 0)
                    {
                        int managerRc = topo.EndEdit();
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_MASS_CONSTRAINT_FAILED",
                            $"GetMassConstraint err={err}; manager EndEdit rc={managerRc}.");
                    }
                    mass.BeginEdit();
                    int preferenceRc = mass.SetMassPreference(SimTopoMassPercent);
                    int valueRc = mass.SetValue(massReduction);
                    int massEndRc = mass.EndEdit();
                    int massManagerRc = topo.EndEdit();
                    if (preferenceRc != 0 || valueRc != 0 || massEndRc != 0 || massManagerRc != 0)
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_MASS_CONSTRAINT_FAILED",
                            $"preference rc={preferenceRc}; value rc={valueRc}; constraint EndEdit rc={massEndRc}; manager EndEdit rc={massManagerRc}.");
                    applied.Add($"mass_reduction={massReduction}% rc=0");
                }

                if (preservedCoords != null && preservedCoords.Count > 0)
                {
                    string faceErr;
                    object[] faces = PickSimFaces(modelDoc, preservedCoords, out faceErr);
                    if (faces == null)
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "FACE_PICK_FAILED", faceErr);

                    topo.BeginEdit();
                    int err;
                    CosWorks.CWTopologyPreservedRegion region = topo.CreatePreservedRegionControl(out err);
                    if (region == null || err != 0)
                    {
                        int managerRc = topo.EndEdit();
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_PRESERVED_REGION_FAILED",
                            $"CreatePreservedRegionControl err={err}; manager EndEdit rc={managerRc}.");
                    }
                    region.BeginEdit();
                    int selectRc = region.SelectFaces((object)faces);
                    int regionEndRc = region.EndEdit();
                    int regionManagerRc = topo.EndEdit();
                    if (selectRc != 0 || regionEndRc != 0 || regionManagerRc != 0)
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_PRESERVED_REGION_FAILED",
                            $"SelectFaces rc={selectRc}; control EndEdit rc={regionEndRc}; manager EndEdit rc={regionManagerRc}.");
                    applied.Add($"preserved_faces={faces.Length} rc=0");
                }

                if (minThickness > 0)
                {
                    topo.BeginEdit();
                    int err;
                    CosWorks.CWTopologyThicknessControl thick = topo.CreateThicknessControl(out err);
                    if (thick == null || err != 0)
                    {
                        int managerRc = topo.EndEdit();
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_THICKNESS_CONTROL_FAILED",
                            $"CreateThicknessControl err={err}; manager EndEdit rc={managerRc}.");
                    }
                    thick.BeginEdit();
                    thick.SetIncludeMinMemberThickness2(true);
                    thick.SetMinimumMemberThickness(minThickness * 1000.0);
                    thick.SetMinimumMemberThicknessUnit(0);
                    int thicknessEndRc = thick.EndEdit();
                    int thicknessManagerRc = topo.EndEdit();
                    if (thicknessEndRc != 0 || thicknessManagerRc != 0)
                        return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                            "TOPOLOGY_THICKNESS_CONTROL_FAILED",
                            $"control EndEdit rc={thicknessEndRc}; manager EndEdit rc={thicknessManagerRc}.");
                    applied.Add($"min_thickness={minThickness * 1000.0}mm rc=0");
                }

                return SimOk(request, modelDoc, true,
                    new List<string> { $"study={studyName}" }.Concat(applied).ToList(),
                    new { study = studyName, applied });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimListStudies(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, false, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var studies = new List<object>();
                int count = sm.StudyCount;
                for (int i = 0; i < count; i++)
                {
                    dynamic s = sm.GetStudy(i);
                    if (s != null)
                        studies.Add(new { index = i, name = (string)s.Name, analysis_type = (int)s.AnalysisType });
                }
                return SimOk(request, modelDoc, false,
                    new List<string> { $"studies={count}" }, new { count, studies });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }

        public ExecutionResponse SimDeleteStudy(ToolRequest request)
        {
            IModelDoc2 modelDoc; dynamic sm;
            var gate = SimGuardEntry(request, true, out modelDoc, out sm);
            if (gate != null) return gate;

            try
            {
                var p = request.Params as JObject;
                string studyName = p?.Value<string>("name");
                if (string.IsNullOrEmpty(studyName))
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "MISSING_PARAMETER", "name is required.");

                int idx;
                if (FindSimStudy(sm, studyName, out idx) == null)
                    return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(),
                        "STUDY_NOT_FOUND", $"No study named '{studyName}'.");

                sm.DeleteStudy(studyName);

                return SimOk(request, modelDoc, true,
                    new List<string> { $"deleted={studyName}" }, new { deleted = studyName });
            }
            catch (COMException ex)
            {
                return BuildFailed(request.OperationId, _guard.GetCurrentStateVersion(), "COM_ERROR", ex.Message);
            }
        }
    }
}
