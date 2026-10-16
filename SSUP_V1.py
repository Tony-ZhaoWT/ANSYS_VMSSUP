def post_started(sender, analysis):  # Do not edit this line
    define_dpf_workflow(analysis)


def define_dpf_workflow(analysis):

    import math
    import mech_dpf
    import Ans.DataProcessing as dpf

    mech_dpf.setExtAPI(ExtAPI)

    # ============================================================
    # USER SETTINGS
    # ============================================================

    # Name of your Static Structural analysis in Mechanical tree
    STATIC_ANALYSIS_NAME = "Static Structural"

    # Frequency at which total stress is required [Hz]
    TARGET_FREQUENCY = 120.0

    # Phase increment [degree]
    # 5 deg -> 72 phase points
    # 2 deg -> more accurate, but slower
    PHASE_STEP = 5.0

    # ============================================================
    # GET ANALYSES
    # ============================================================

    static_analysis = ExtAPI.DataModel.AnalysisByName(
        STATIC_ANALYSIS_NAME
    )

    harmonic_analysis = analysis

    static_ds = dpf.DataSources(static_analysis.ResultFileName)
    harmonic_ds = dpf.DataSources(harmonic_analysis.ResultFileName)

    # ============================================================
    # FIND HARMONIC RESULT SET CLOSEST TO TARGET FREQUENCY
    # ============================================================

    tf_op = dpf.operators.metadata.time_freq_provider()
    tf_op.inputs.data_sources.Connect(harmonic_ds)

    tf_support = tf_op.outputs.time_freq_support.GetData()

    frequencies = list(tf_support.TimeFreqs.Data)

    if len(frequencies) == 0:
        raise Exception("No harmonic frequencies were found.")

    closest_index = min(
        range(len(frequencies)),
        key=lambda i: abs(frequencies[i] - TARGET_FREQUENCY)
    )

    harmonic_set_id = closest_index + 1
    actual_frequency = frequencies[closest_index]

    ExtAPI.Log.WriteMessage(
        "Requested frequency = " +
        str(TARGET_FREQUENCY) +
        " Hz"
    )

    ExtAPI.Log.WriteMessage(
        "Using harmonic frequency = " +
        str(actual_frequency) +
        " Hz, set = " +
        str(harmonic_set_id)
    )

    # ============================================================
    # STATIC STRESS
    # ============================================================
    #
    # Read full 6-component stress tensor:
    #
    # [Sx, Sy, Sz, Sxy, Syz, Sxz]
    #
    # Nodal averaging is requested here.
    # ============================================================

    static_tf = dpf.operators.metadata.time_freq_provider()
    static_tf.inputs.data_sources.Connect(static_ds)

    static_support = static_tf.outputs.time_freq_support.GetData()

    static_set_id = static_support.NumberSets

    static_scope = dpf.Scoping()
    static_scope.Ids = [static_set_id]

    static_stress_op = dpf.operators.result.stress()

    static_stress_op.inputs.data_sources.Connect(static_ds)
    static_stress_op.inputs.time_scoping.Connect(static_scope)
    static_stress_op.inputs.requested_location.Connect("Nodal")

    static_fc = static_stress_op.outputs.fields_container.GetData()

    static_field = static_fc[0]

    # ============================================================
    # HARMONIC COMPLEX STRESS
    # ============================================================

    harmonic_scope = dpf.Scoping()
    harmonic_scope.Ids = [harmonic_set_id]

    harmonic_stress_op = dpf.operators.result.stress()

    harmonic_stress_op.inputs.data_sources.Connect(harmonic_ds)
    harmonic_stress_op.inputs.time_scoping.Connect(harmonic_scope)
    harmonic_stress_op.inputs.requested_location.Connect("Nodal")

    harmonic_fc = (
        harmonic_stress_op.outputs.fields_container.GetData()
    )

    # Harmonic result is stored as:
    #
    # complex = 0 -> real part
    # complex = 1 -> imaginary part
    #
    # For one frequency this normally gives two fields.

    if len(harmonic_fc) < 2:
        raise Exception(
            "Harmonic stress did not return both real and "
            "imaginary fields. Check harmonic result expansion."
        )

    harmonic_real = harmonic_fc[0]
    harmonic_imag = harmonic_fc[1]

    # ============================================================
    # CHECK COMMON NODE IDS
    # ============================================================

    static_ids = set(static_field.ScopingIds)
    real_ids = set(harmonic_real.ScopingIds)
    imag_ids = set(harmonic_imag.ScopingIds)

    common_ids = sorted(
        list(static_ids & real_ids & imag_ids)
    )

    if len(common_ids) == 0:
        raise Exception(
            "No common nodes between Static and Harmonic results."
        )

    ExtAPI.Log.WriteMessage(
        "Common nodes used = " + str(len(common_ids))
    )

    # ============================================================
    # VON MISES FUNCTION
    # ============================================================

    def von_mises(s):

        sx = s[0]
        sy = s[1]
        sz = s[2]

        sxy = s[3]
        syz = s[4]
        sxz = s[5]

        vm2 = (
            0.5 * (
                (sx - sy) ** 2 +
                (sy - sz) ** 2 +
                (sz - sx) ** 2
            )
            +
            3.0 * (
                sxy ** 2 +
                syz ** 2 +
                sxz ** 2
            )
        )

        if vm2 < 0.0:
            vm2 = 0.0

        return math.sqrt(vm2)

    # ============================================================
    # PHASE SWEEP
    # ============================================================
    #
    # sigma(theta)
    #
    # = sigma_static
    # + sigma_real*cos(theta)
    # - sigma_imag*sin(theta)
    #
    # Store maximum VM over complete cycle.
    # ============================================================

    max_vm = []

    number_phases = int(
        round(360.0 / PHASE_STEP)
    )

    for counter, nid in enumerate(common_ids):

        s0 = static_field.GetEntityDataById(nid)
        sr = harmonic_real.GetEntityDataById(nid)
        si = harmonic_imag.GetEntityDataById(nid)

        maximum = -1.0

        for p in range(number_phases):

            phase_deg = p * PHASE_STEP
            phase_rad = math.radians(phase_deg)

            c = math.cos(phase_rad)
            sn = math.sin(phase_rad)

            total = [
                s0[j] +
                sr[j] * c -
                si[j] * sn
                for j in range(6)
            ]

            vm = von_mises(total)

            if vm > maximum:
                maximum = vm

        max_vm.append(maximum)

    # ============================================================
    # CREATE CUSTOM DPF FIELD
    # ============================================================

    result_field = dpf.FieldsFactory.CreateScalarField(
        numEntities=len(common_ids),
        location=dpf.locations.nodal
    )

    result_field.Scoping.Ids = common_ids
    result_field.Data = max_vm

    # Same unit as stress result
    result_field.Unit = static_field.Unit

    # ============================================================
    # SEND FIELD BACK TO MECHANICAL AS CONTOUR
    # ============================================================

    forward_op = dpf.operators.utility.forward_field()

    forward_op.inputs.field.Connect(result_field)

    workflow = dpf.Workflow()

    workflow.Add(forward_op)

    workflow.SetOutputContour(forward_op)

    workflow.Record("wf_id", False)

    this.WorkflowId = workflow.GetRecordedId()

    ExtAPI.Log.WriteMessage(
        "Maximum total von Mises contour created at " +
        str(actual_frequency) +
        " Hz."
    )