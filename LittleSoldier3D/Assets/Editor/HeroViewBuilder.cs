using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class HeroViewBuilder
{
    [MenuItem("LittleSoldier/Setup Hero View")]
    public static void Setup()
    {
        GameObject player = GameObject.Find("Player");
        if (player == null)
        {
            Debug.LogError("Player was not found. Run LittleSoldier -> Build Training Scene first.");
            return;
        }

        Camera cam = player.GetComponentInChildren<Camera>(true);
        if (cam == null && Camera.main != null)
            cam = Camera.main;
        if (cam == null)
        {
            GameObject cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cameraObject.transform.SetParent(player.transform);
            cameraObject.transform.localPosition = new Vector3(0f, 0.6f, 0f);
            cameraObject.transform.localRotation = Quaternion.identity;
            cam = cameraObject.AddComponent<Camera>();
            cameraObject.AddComponent<AudioListener>();
        }

        if (cam.transform.parent != player.transform)
        {
            cam.transform.SetParent(player.transform);
            cam.transform.localPosition = new Vector3(0f, 0.6f, 0f);
            cam.transform.localRotation = Quaternion.identity;
        }

        Transform hero = player.transform.Find("HeroModel");
        if (hero == null)
            hero = CreateHeroModel(player.transform).transform;

        ViewSwitcher vs = cam.GetComponent<ViewSwitcher>();
        if (vs == null)
            vs = cam.gameObject.AddComponent<ViewSwitcher>();

        vs.heroModel = hero;
        SetHeroVisible(hero, false);

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("Hero view is ready. Press Play, then press V to switch first/third person.");
    }

    private static GameObject CreateHeroModel(Transform parent)
    {
        Material uniform = MakeMat(new Color(0.20f, 0.42f, 0.24f));
        Material vest = MakeMat(new Color(0.12f, 0.16f, 0.13f));
        Material skin = MakeMat(new Color(1.00f, 0.72f, 0.52f));
        Material hair = MakeMat(new Color(0.05f, 0.04f, 0.035f));
        Material gold = MakeMat(new Color(0.95f, 0.72f, 0.22f));

        GameObject root = new GameObject("HeroModel");
        root.transform.SetParent(parent);
        root.transform.localPosition = new Vector3(0f, -0.1f, 0f);
        root.transform.localRotation = Quaternion.identity;

        CreatePart(root.transform, "Body", PrimitiveType.Capsule, new Vector3(0f, 0.05f, 0f), Quaternion.identity, new Vector3(0.45f, 0.62f, 0.45f), uniform);
        CreatePart(root.transform, "Vest", PrimitiveType.Cube, new Vector3(0f, 0.08f, 0.23f), Quaternion.identity, new Vector3(0.55f, 0.65f, 0.12f), vest);
        CreatePart(root.transform, "Head", PrimitiveType.Sphere, new Vector3(0f, 0.92f, 0f), Quaternion.identity, new Vector3(0.48f, 0.48f, 0.48f), skin);
        CreatePart(root.transform, "Hair", PrimitiveType.Sphere, new Vector3(0f, 1.08f, -0.02f), Quaternion.identity, new Vector3(0.50f, 0.24f, 0.50f), hair);
        CreatePart(root.transform, "LeftArm", PrimitiveType.Capsule, new Vector3(-0.45f, 0.12f, 0f), Quaternion.Euler(0f, 0f, 20f), new Vector3(0.16f, 0.40f, 0.16f), uniform);
        CreatePart(root.transform, "RightArm", PrimitiveType.Capsule, new Vector3(0.45f, 0.12f, 0f), Quaternion.Euler(0f, 0f, -20f), new Vector3(0.16f, 0.40f, 0.16f), uniform);
        CreatePart(root.transform, "LeftLeg", PrimitiveType.Capsule, new Vector3(-0.18f, -0.66f, 0f), Quaternion.identity, new Vector3(0.17f, 0.36f, 0.17f), uniform);
        CreatePart(root.transform, "RightLeg", PrimitiveType.Capsule, new Vector3(0.18f, -0.66f, 0f), Quaternion.identity, new Vector3(0.17f, 0.36f, 0.17f), uniform);
        CreatePart(root.transform, "Badge", PrimitiveType.Cube, new Vector3(0f, 0.24f, 0.31f), Quaternion.identity, new Vector3(0.22f, 0.18f, 0.04f), gold);

        return root;
    }

    private static GameObject CreatePart(Transform parent, string name, PrimitiveType type, Vector3 localPosition, Quaternion localRotation, Vector3 localScale, Material material)
    {
        GameObject part = GameObject.CreatePrimitive(type);
        part.name = name;
        part.transform.SetParent(parent);
        part.transform.localPosition = localPosition;
        part.transform.localRotation = localRotation;
        part.transform.localScale = localScale;

        Collider collider = part.GetComponent<Collider>();
        if (collider != null)
            Object.DestroyImmediate(collider);

        Renderer renderer = part.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = material;

        return part;
    }

    private static Material MakeMat(Color color)
    {
        Shader shader = Shader.Find("Standard");
        if (shader == null)
            shader = Shader.Find("Universal Render Pipeline/Lit");

        Material material = new Material(shader);
        if (material.HasProperty("_Color"))
            material.SetColor("_Color", color);
        if (material.HasProperty("_BaseColor"))
            material.SetColor("_BaseColor", color);
        return material;
    }

    private static void SetHeroVisible(Transform hero, bool visible)
    {
        Renderer[] renderers = hero.GetComponentsInChildren<Renderer>();
        foreach (Renderer renderer in renderers)
            renderer.enabled = visible;
    }
}
